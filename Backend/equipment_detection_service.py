import asyncio
import io
import threading
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps, UnidentifiedImageError


MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "equipment_vision"
    / "yolox_nano_coco_v1"
    / "yolox_nano.onnx"
)

INPUT_SIZE = 416
CONFIDENCE_THRESHOLD = 0.35
NMS_THRESHOLD = 0.45
MAX_FRAME_SIZE = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_DIMENSION = 4096
MAX_DETECTIONS = 30

COCO_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "airplane",
    "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet",
    "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
)

_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session

    if _session is not None:
        return _session

    with _session_lock:
        if _session is None:
            if not MODEL_PATH.is_file():
                raise RuntimeError("Equipment detection model is missing.")

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            _session = ort.InferenceSession(
                str(MODEL_PATH),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )

    return _session


def _preprocess(image_bytes, mime_type):
    if not image_bytes:
        raise ValueError("The image is empty.")

    if len(image_bytes) > MAX_FRAME_SIZE:
        raise ValueError("Frame exceeds the 2 MB limit.")

    allowed = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    if mime_type not in allowed:
        raise ValueError("Unsupported image format.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            if source.format != allowed[mime_type]:
                raise ValueError("Image content does not match its MIME type.")

            image = ImageOps.exif_transpose(source).convert("RGB")
            width, height = image.size

            if (
                width <= 0
                or height <= 0
                or width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise ValueError("Image dimensions exceed the allowed limit.")

            image_array = np.asarray(image)[:, :, ::-1].copy()

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded image is invalid.") from exc

    ratio = min(INPUT_SIZE / width, INPUT_SIZE / height)
    resized_width = max(1, int(width * ratio))
    resized_height = max(1, int(height * ratio))

    resized = Image.fromarray(image_array[:, :, ::-1]).resize(
        (resized_width, resized_height),
        Image.Resampling.BILINEAR,
    )
    resized_bgr = np.asarray(resized)[:, :, ::-1]

    canvas = np.full(
        (INPUT_SIZE, INPUT_SIZE, 3),
        114,
        dtype=np.uint8,
    )
    canvas[:resized_height, :resized_width] = resized_bgr

    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None, ...]

    return tensor, width, height, ratio


def _nms(boxes, scores, threshold):
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]
    kept = []

    while order.size:
        current = int(order[0])
        kept.append(current)

        if order.size == 1:
            break

        remaining = order[1:]

        xx1 = np.maximum(x1[current], x1[remaining])
        yy1 = np.maximum(y1[current], y1[remaining])
        xx2 = np.minimum(x2[current], x2[remaining])
        yy2 = np.minimum(y2[current], y2[remaining])

        intersection = (
            np.maximum(0, xx2 - xx1)
            * np.maximum(0, yy2 - yy1)
        )

        union = areas[current] + areas[remaining] - intersection
        overlap = intersection / np.maximum(union, 1e-9)

        order = remaining[overlap <= threshold]

    return kept


def _decode(output, width, height, ratio):
    predictions = np.asarray(output, dtype=np.float32)

    if predictions.ndim == 3:
        predictions = predictions[0]

    if predictions.shape != (3549, 85):
        raise RuntimeError("Unexpected YOLOX model output shape.")

    grids = []
    strides = []

    for stride in (8, 16, 32):
        grid_size = INPUT_SIZE // stride
        grid_y, grid_x = np.meshgrid(
            np.arange(grid_size),
            np.arange(grid_size),
            indexing="ij",
        )

        grid = np.stack((grid_x, grid_y), axis=-1).reshape(-1, 2)
        grids.append(grid)
        strides.append(
            np.full((grid.shape[0], 1), stride, dtype=np.float32)
        )

    grid = np.concatenate(grids, axis=0).astype(np.float32)
    stride = np.concatenate(strides, axis=0)

    boxes_xy = (predictions[:, :2] + grid) * stride
    boxes_wh = np.exp(
        np.clip(predictions[:, 2:4], -10, 10)
    ) * stride

    boxes = np.concatenate(
        (
            boxes_xy - boxes_wh / 2,
            boxes_xy + boxes_wh / 2,
        ),
        axis=1,
    )

    class_scores = predictions[:, 5:85]
    class_ids = np.argmax(class_scores, axis=1)
    scores = predictions[:, 4] * class_scores[
        np.arange(len(class_scores)), class_ids
    ]

    valid = np.isfinite(scores) & (scores >= CONFIDENCE_THRESHOLD)
    boxes = boxes[valid]
    scores = scores[valid]
    class_ids = class_ids[valid]

    if not len(boxes):
        return []

    boxes /= ratio
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, width)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, height)

    results = []

    for class_id in np.unique(class_ids):
        class_mask = class_ids == class_id
        class_boxes = boxes[class_mask]
        class_scores = scores[class_mask]

        kept = _nms(class_boxes, class_scores, NMS_THRESHOLD)

        for index in kept:
            x1, y1, x2, y2 = class_boxes[index]

            if x2 <= x1 or y2 <= y1:
                continue

            results.append({
                "class_id": int(class_id),
                "label": COCO_CLASSES[int(class_id)],
                "confidence": round(float(class_scores[index]), 4),
                "x1": round(float(x1 / width), 6),
                "y1": round(float(y1 / height), 6),
                "x2": round(float(x2 / width), 6),
                "y2": round(float(y2 / height), 6),
            })

    results.sort(key=lambda item: item["confidence"], reverse=True)

    return results[:MAX_DETECTIONS]


def detect_objects(image_bytes, mime_type):
    tensor, width, height, ratio = _preprocess(
        image_bytes,
        mime_type,
    )

    session = _get_session()
    input_name = session.get_inputs()[0].name

    started = time.perf_counter()
    output = session.run(None, {input_name: tensor})[0]
    inference_ms = (time.perf_counter() - started) * 1000

    detections = _decode(output, width, height, ratio)

    return {
        "model": "YOLOX-Nano COCO",
        "image_width": width,
        "image_height": height,
        "inference_ms": round(inference_ms, 2),
        "detections": detections,
        "limitations": (
            "Generic COCO classes only. Industrial equipment "
            "identification requires separate validation or a "
            "specialized trained model."
        ),
    }


async def detect_objects_async(image_bytes, mime_type):
    return await asyncio.to_thread(
        detect_objects,
        image_bytes,
        mime_type,
    )
