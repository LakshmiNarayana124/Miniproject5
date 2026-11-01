
import { useEffect, useRef, useState } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import {
  OrbitControls,
  ContactShadows,
  Html,
} from '@react-three/drei'
import * as THREE from 'three'

// ==================================================
// HARDWARE COMPONENT INFORMATION
// ==================================================

const COMPONENTS = [
  {
    id: 'raspberry',
    name: 'Raspberry Pi',
    category: 'Processing Unit',
    color: '#277a50',
    purpose: 'Main processing unit that runs IntelliWatch and communicates with the sensors.',
    pins: ['3.3V', '5V', 'GND', 'GPIO', 'SDA', 'SCL', 'SPI'],
  },
  {
    id: 'breadboard',
    name: 'Breadboard',
    category: 'Prototyping',
    color: '#e5e7eb',
    purpose: 'A reusable prototyping board for connecting electronic components without soldering.',
    pins: ['Power rails', 'Terminal strips', 'Connection rows'],
  },
  {
    id: 'adxl',
    name: 'ADXL345',
    category: 'Vibration Sensor',
    color: '#2563eb',
    purpose: 'A three-axis accelerometer used to measure acceleration and monitor vibration.',
    pins: ['VCC', 'GND', 'SDA', 'SCL', 'CS', 'SDO', 'INT1', 'INT2'],
  },
  {
    id: 'acs',
    name: 'ACS712',
    category: 'Current Sensor',
    color: '#0d9488',
    purpose: 'Measures current using the Hall-effect principle and provides an analog output.',
    pins: ['VCC', 'GND', 'OUT', 'IP+', 'IP-'],
  },
  {
    id: 'ds18',
    name: 'DS18B20',
    category: 'Temperature Sensor',
    color: '#dc7c32',
    purpose: 'A digital temperature sensor using the 1-Wire communication protocol.',
    pins: ['VDD', 'DATA', 'GND'],
  },
  {
    id: 'ads',
    name: 'ADS1115',
    category: 'Analog-to-Digital Converter',
    color: '#7c3aed',
    purpose: 'Converts analog signals into digital readings so the Raspberry Pi can process them.',
    pins: ['VDD', 'GND', 'SDA', 'SCL', 'ADDR', 'A0', 'A1', 'A2', 'A3'],
  },
  {
    id: 'relay',
    name: 'Relay Module',
    category: 'Switching Module',
    color: '#b45309',
    purpose: 'An electrically controlled switch for demonstrating low-voltage load control.',
    pins: ['VCC', 'GND', 'IN', 'COM', 'NO', 'NC'],
  },
  {
    id: 'lcd',
    name: '16×2 I²C LCD',
    category: 'Display Module',
    color: '#0891b2',
    purpose: 'Displays messages, sensor readings and system status using an I²C interface.',
    pins: ['VCC', 'GND', 'SDA', 'SCL'],
  },
]

const WORKSPACE_LIMITS = {
  x: 4.65,
  z: 2.35,
}

const CAMERA_VIEWS = {
  default: [9, 8, 11],
  front: [0, 7, 13],
  back: [0, 7, -13],
  left: [-13, 7, 0],
  right: [13, 7, 0],
  top: [0, 15, 0.01],
  bottom: [0, -15, 0.01],
}

// ==================================================
// REUSABLE 3D MODELS
// ==================================================

function Board({
  color = '#176b4b',
  children,
  onClick,
  selected,
}) {
  return (
    <group onClick={onClick}>
      <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.65, 0.2, 1.15]} />
        <meshStandardMaterial
          color={selected ? '#38bdf8' : color}
          roughness={0.65}
          metalness={0.2}
        />
      </mesh>
      {children}
    </group>
  )
}

function Chip({
  position = [0, 0, 0],
  size = [0.55, 0.16, 0.45],
  color = '#171b24',
}) {
  return (
    <mesh position={position} castShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} roughness={0.4} />
    </mesh>
  )
}

function Pins({
  count = 8,
  position = [0, 0.25, 0],
  spacing = 0.16,
  direction = 'x',
}) {
  return (
    <group position={position}>
      {Array.from({ length: count }, (_, i) => (
        <mesh
          key={i}
          position={
            direction === 'x'
              ? [(i - (count - 1) / 2) * spacing, 0, 0]
              : [0, 0, (i - (count - 1) / 2) * spacing]
          }
          castShadow
        >
          <boxGeometry args={[0.045, 0.25, 0.045]} />
          <meshStandardMaterial
            color="#d6b76b"
            metalness={0.8}
            roughness={0.25}
          />
        </mesh>
      ))}
    </group>
  )
}

// ==================================================
// INDIVIDUAL HARDWARE MODELS
// ==================================================

function RaspberryPi({ onClick, selected }) {
  return (
    <Board color="#176b4b" onClick={onClick} selected={selected}>
      <Chip position={[0, 0.25, 0]} size={[0.55, 0.16, 0.5]} />
      <Pins count={20} position={[0, 0.3, -0.47]} spacing={0.065} />

      {[-0.58, -0.2, 0.2].map((x, i) => (
        <mesh key={i} position={[x, 0.25, 0.48]}>
          <boxGeometry args={[0.3, 0.3, 0.2]} />
          <meshStandardMaterial color="#9ca3af" metalness={0.8} />
        </mesh>
      ))}

      <mesh position={[0.58, 0.25, -0.2]}>
        <boxGeometry args={[0.2, 0.24, 0.3]} />
        <meshStandardMaterial color="#a3a3a3" metalness={0.7} />
      </mesh>
    </Board>
  )
}

function Breadboard({ onClick, selected }) {
  return (
    <group onClick={onClick}>
      <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.85, 0.2, 1.3]} />
        <meshStandardMaterial color={selected ? '#bae6fd' : '#e5e7eb'} />
      </mesh>

      {Array.from({ length: 12 }, (_, row) =>
        Array.from({ length: 17 }, (_, col) => (
          <mesh
            key={`${row}-${col}`}
            position={[
              -0.78 + col * 0.097,
              0.225,
              -0.48 + row * 0.087,
            ]}
          >
            <cylinderGeometry args={[0.018, 0.018, 0.012, 8]} />
            <meshStandardMaterial color="#596575" metalness={0.5} />
          </mesh>
        )),
      )}
    </group>
  )
}

function ADXL345({ onClick, selected }) {
  return (
    <Board color="#1765a5" onClick={onClick} selected={selected}>
      <Chip position={[0, 0.25, 0]} size={[0.55, 0.14, 0.55]} />
      <Pins count={8} position={[0, 0.3, -0.47]} />

      <mesh position={[0.55, 0.23, 0.25]}>
        <cylinderGeometry args={[0.08, 0.08, 0.12, 12]} />
        <meshStandardMaterial color="#d1d5db" metalness={0.7} />
      </mesh>
    </Board>
  )
}

function ACS712({ onClick, selected }) {
  return (
    <Board color="#0f766e" onClick={onClick} selected={selected}>
      <Chip position={[0, 0.26, -0.1]} size={[0.6, 0.16, 0.55]} />
      <Pins count={3} position={[0, 0.3, -0.48]} />

      <mesh position={[0, 0.25, 0.43]}>
        <boxGeometry args={[1.2, 0.28, 0.25]} />
        <meshStandardMaterial color="#9ca3af" metalness={0.8} />
      </mesh>
    </Board>
  )
}

function DS18B20({ onClick, selected }) {
  return (
    <group onClick={onClick}>
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[1.5, 0.16, 0.9]} />
        <meshStandardMaterial color={selected ? '#bae6fd' : '#e5e7eb'} />
      </mesh>

      <mesh position={[0, 0.48, 0]}>
        <cylinderGeometry args={[0.3, 0.3, 0.6, 24]} />
        <meshStandardMaterial color="#aeb7c2" metalness={0.8} roughness={0.3} />
      </mesh>

      <mesh position={[0, 0.8, 0]}>
        <sphereGeometry args={[0.3, 24, 16]} />
        <meshStandardMaterial color="#cbd5e1" metalness={0.8} />
      </mesh>

      <Pins count={3} position={[0, 0.3, 0.5]} spacing={0.2} />
    </group>
  )
}

function ADS1115({ onClick, selected }) {
  return (
    <Board color="#6937a6" onClick={onClick} selected={selected}>
      <Chip position={[0, 0.25, 0]} size={[0.5, 0.15, 0.45]} />
      <Pins count={5} position={[-0.55, 0.3, -0.47]} />
      <Pins count={5} position={[0.55, 0.3, -0.47]} />

      <mesh position={[0, 0.24, 0.45]}>
        <boxGeometry args={[0.4, 0.15, 0.18]} />
        <meshStandardMaterial color="#d1d5db" />
      </mesh>
    </Board>
  )
}

function RelayModule({ onClick, selected }) {
  return (
    <Board color="#16734c" onClick={onClick} selected={selected}>
      <mesh position={[0, 0.34, 0]}>
        <boxGeometry args={[0.85, 0.4, 0.65]} />
        <meshStandardMaterial color="#2563eb" roughness={0.5} />
      </mesh>

      <Pins count={3} position={[-0.55, 0.3, -0.47]} />
      <Pins count={3} position={[0.55, 0.3, -0.47]} />

      <mesh position={[0, 0.25, 0.47]}>
        <cylinderGeometry args={[0.1, 0.1, 0.16, 16]} />
        <meshStandardMaterial color="#fbbf24" metalness={0.6} />
      </mesh>
    </Board>
  )
}

function LCD({ onClick, selected }) {
  return (
    <group onClick={onClick}>
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[1.85, 0.22, 1.1]} />
        <meshStandardMaterial color={selected ? '#bae6fd' : '#1e293b'} />
      </mesh>

      <mesh position={[0, 0.25, 0]}>
        <boxGeometry args={[1.45, 0.08, 0.55]} />
        <meshStandardMaterial color="#064e3b" metalness={0.2} />
      </mesh>

      <mesh position={[0, 0.3, 0]}>
        <boxGeometry args={[1.35, 0.015, 0.45]} />
        <meshStandardMaterial
          color="#65d6a1"
          emissive="#166534"
          emissiveIntensity={0.5}
        />
      </mesh>

      <Pins count={4} position={[0, 0.3, 0.52]} />
    </group>
  )
}

// ==================================================
// MODEL ROUTER
// ==================================================

function HardwareModel({
  component,
  selected,
  onSelect,
}) {
  const props = {
    selected,
    onClick: (event) => {
      event.stopPropagation()
      onSelect(component)
    },
  }

  const models = {
    raspberry: RaspberryPi,
    breadboard: Breadboard,
    adxl: ADXL345,
    acs: ACS712,
    ds18: DS18B20,
    ads: ADS1115,
    relay: RelayModule,
    lcd: LCD,
  }

  const Model = models[component.componentId]

  return (
    <group
      position={component.position}
      rotation={[0, component.rotationY || 0, 0]}
    >
      <Model {...props} />

      {selected && (
        <mesh position={[0, 1.15, 0]}>
          <sphereGeometry args={[0.07, 16, 16]} />
          <meshBasicMaterial color="#38bdf8" />
        </mesh>
      )}

      <Html position={[0, 0.95, 0]} center distanceFactor={9}>
        <div
          style={{
            background: selected ? '#0369a1' : 'rgba(15,23,42,0.9)',
            color: 'white',
            padding: '5px 9px',
            borderRadius: '6px',
            fontSize: '11px',
            whiteSpace: 'nowrap',
            border: selected ? '1px solid #7dd3fc' : '1px solid #475569',
            pointerEvents: 'none',
          }}
        >
          {component.name}
        </div>
      </Html>
    </group>
  )
}

// ==================================================
// WORKSPACE DROP + CAMERA CONTROLS
// ==================================================

function Workspace({
  placedComponents,
  selectedInstanceId,
  onSelect,
  onPlaceAt,
  onDeselect,
  onDropComponent,
  cameraView,
}) {
  const { camera, gl } = useThree()
  const controlsRef = useRef()

  // Drag a component card and drop it into the 3D workspace.
  useEffect(() => {
    const canvas = gl.domElement

    const handleDragOver = (event) => {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
    }

    const handleDrop = (event) => {
      event.preventDefault()

      const componentId = event.dataTransfer.getData('text/plain')
      if (!COMPONENTS.some(component => component.id === componentId)) return

      const bounds = canvas.getBoundingClientRect()

      const pointer = new THREE.Vector2(
        ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
        -((event.clientY - bounds.top) / bounds.height) * 2 + 1,
      )

      const raycaster = new THREE.Raycaster()
      raycaster.setFromCamera(pointer, camera)

      const workbenchPlane = new THREE.Plane(
        new THREE.Vector3(0, 1, 0),
        0,
      )

      const intersection = new THREE.Vector3()
      const hit = raycaster.ray.intersectPlane(workbenchPlane, intersection)

      if (!hit) return

      onDropComponent(componentId, [
        intersection.x,
        0,
        intersection.z,
      ])
    }

    canvas.addEventListener('dragover', handleDragOver)
    canvas.addEventListener('drop', handleDrop)

    return () => {
      canvas.removeEventListener('dragover', handleDragOver)
      canvas.removeEventListener('drop', handleDrop)
    }
  }, [gl, camera, onDropComponent])

  // Camera presets: default, front, back, left, right, top and bottom.
  useEffect(() => {
    const position = CAMERA_VIEWS[cameraView] || CAMERA_VIEWS.default

    camera.position.set(...position)
    camera.up.set(0, 1, 0)
    camera.lookAt(0, 0, 0)

    if (controlsRef.current) {
      controlsRef.current.target.set(0, 0, 0)
      controlsRef.current.update()
    }
  }, [cameraView, camera])

  return (
    <>
      <color attach="background" args={['#101820']} />

      <ambientLight intensity={1.1} />

      <directionalLight
        position={[5, 9, 6]}
        intensity={2}
        castShadow
      />

      <pointLight position={[-5, 5, -5]} intensity={1} color="#60a5fa" />

      {/* Workbench base */}
      <mesh position={[0, -0.3, 0]} receiveShadow castShadow>
        <boxGeometry args={[11.5, 0.5, 6.2]} />
        <meshStandardMaterial
          color="#263548"
          roughness={0.65}
          metalness={0.25}
        />
      </mesh>

      {/* Workbench top */}
      <mesh position={[0, -0.03, 0]}>
        <boxGeometry args={[11.3, 0.04, 6]} />
        <meshStandardMaterial color="#172536" roughness={0.8} />
      </mesh>

      <gridHelper
        args={[11, 44, '#52708d', '#34495e']}
        position={[0, 0.001, 0]}
      />

      {/* Invisible placement surface */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.015, 0]}
        onClick={(event) => {
          event.stopPropagation()

          onPlaceAt([
            event.point.x,
            0,
            event.point.z,
          ])
        }}
      >
        <planeGeometry args={[11.1, 5.8]} />
        <meshBasicMaterial
          transparent
          opacity={0}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Placed hardware */}
      {placedComponents.map(component => (
        <HardwareModel
          key={component.instanceId}
          component={component}
          selected={selectedInstanceId === component.instanceId}
          onSelect={onSelect}
        />
      ))}

      <ContactShadows
        position={[0, -0.04, 0]}
        opacity={0.35}
        scale={14}
        blur={2.5}
        far={5}
      />

      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.57, 0]}
        receiveShadow
      >
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#101820" />
      </mesh>

      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        minDistance={3}
        maxDistance={24}
        minPolarAngle={0.001}
        maxPolarAngle={Math.PI - 0.001}
        screenSpacePanning
      />
    </>
  )
}

// ==================================================
// MAIN EXPLORER
// ==================================================

export default function SensorExplorer() {
  const [placedComponents, setPlacedComponents] = useState([])
  const [selectedInstanceId, setSelectedInstanceId] = useState(null)
  const [selectedComponentId, setSelectedComponentId] = useState(null)
  const [pendingComponentId, setPendingComponentId] = useState(null)
  const [movingInstanceId, setMovingInstanceId] = useState(null)

  const [undoStack, setUndoStack] = useState([])
  const [redoStack, setRedoStack] = useState([])

  const [cameraView, setCameraView] = useState('default')
  const nextId = useRef(1)

  // Save every workspace edit so it can be undone.
  const commitWorkspace = (nextComponents) => {
    setUndoStack(previous => [
      ...previous,
      placedComponents,
    ].slice(-50))

    setRedoStack([])
    setPlacedComponents(nextComponents)
  }

  const clampPosition = (position) => [
    Math.max(-WORKSPACE_LIMITS.x, Math.min(WORKSPACE_LIMITS.x, position[0])),
    0,
    Math.max(-WORKSPACE_LIMITS.z, Math.min(WORKSPACE_LIMITS.z, position[2])),
  ]

  const createComponent = (componentId, position) => {
    const info = COMPONENTS.find(component => component.id === componentId)
    if (!info) return

    const instance = {
      instanceId: `${componentId}-${nextId.current++}`,
      componentId,
      name: info.name,
      position: clampPosition(position),
      rotationY: 0,
    }

    commitWorkspace([...placedComponents, instance])

    setSelectedInstanceId(instance.instanceId)
    setSelectedComponentId(componentId)
    setPendingComponentId(null)
    setMovingInstanceId(null)
  }

  // Click-to-place and reposition using the workbench.
  const handlePlaceAt = (position) => {
    if (pendingComponentId) {
      createComponent(pendingComponentId, position)
      return
    }

    if (movingInstanceId) {
      const next = placedComponents.map(component =>
        component.instanceId === movingInstanceId
          ? { ...component, position: clampPosition(position) }
          : component,
      )

      commitWorkspace(next)
      setMovingInstanceId(null)
      return
    }

    setSelectedInstanceId(null)
    setSelectedComponentId(null)
    setPendingComponentId(null)
  }

  // HTML drag-and-drop placement.
  const handleDropComponent = (componentId, position) => {
    createComponent(componentId, position)
  }

  const handleSelectModel = (component) => {
    setSelectedInstanceId(component.instanceId)
    setSelectedComponentId(component.componentId)
    setPendingComponentId(null)
    setMovingInstanceId(null)
  }

  // Select a component from the component panel.
  const handleChooseComponent = (componentId) => {
    setPendingComponentId(componentId)
    setSelectedComponentId(componentId)
    setSelectedInstanceId(null)
    setMovingInstanceId(null)
  }

  // Deselect everything.
  const handleDeselect = () => {
    setSelectedInstanceId(null)
    setSelectedComponentId(null)
    setPendingComponentId(null)
    setMovingInstanceId(null)
  }

  // Move an already placed component.
  const handleMove = () => {
    if (!selectedInstanceId) return

    if (movingInstanceId === selectedInstanceId) {
      setMovingInstanceId(null)
    } else {
      setMovingInstanceId(selectedInstanceId)
      setPendingComponentId(null)
    }
  }

  // Rotate selected component by 15 degrees.
  const handleRotate = (direction) => {
    if (!selectedInstanceId) return

    const next = placedComponents.map(component =>
      component.instanceId === selectedInstanceId
        ? {
            ...component,
            rotationY: (component.rotationY || 0) + direction * (Math.PI / 12),
          }
        : component,
    )

    commitWorkspace(next)
  }

  // Remove selected component.
  const handleRemove = () => {
    if (!selectedInstanceId) return

    const next = placedComponents.filter(
      component => component.instanceId !== selectedInstanceId,
    )

    commitWorkspace(next)
    handleDeselect()
  }

  // Undo.
  const handleUndo = () => {
    if (undoStack.length === 0) return

    const previous = undoStack[undoStack.length - 1]

    setRedoStack(stack => [...stack, placedComponents])
    setPlacedComponents(previous)
    setUndoStack(stack => stack.slice(0, -1))
    handleDeselect()
  }

  // Redo.
  const handleRedo = () => {
    if (redoStack.length === 0) return

    const next = redoStack[redoStack.length - 1]

    setUndoStack(stack => [...stack, placedComponents])
    setPlacedComponents(next)
    setRedoStack(stack => stack.slice(0, -1))
    handleDeselect()
  }

  // Clear the complete workspace.
  const handleClear = () => {
    if (placedComponents.length === 0) return

    const confirmed = window.confirm(
      'Clear all components from the workspace?',
    )

    if (!confirmed) return

    commitWorkspace([])
    handleDeselect()
  }

  const selectedComponent = COMPONENTS.find(
    component => component.id === selectedComponentId,
  )

  const selectedInstance = placedComponents.find(
    component => component.instanceId === selectedInstanceId,
  )

  const buttonStyle = {
    padding: '9px 13px',
    borderRadius: '8px',
    border: '1px solid var(--border)',
    background: 'var(--bg-card)',
    color: 'var(--text-h)',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 600,
  }

  const disabledButtonStyle = {
    ...buttonStyle,
    opacity: 0.4,
    cursor: 'not-allowed',
  }

  const cameraButtonStyle = {
    ...buttonStyle,
    background: 'rgba(10,18,28,0.92)',
    color: '#dbeafe',
    border: '1px solid #475569',
    minWidth: '58px',
  }

  return (
    <main
      style={{
        padding: '24px',
        color: 'var(--text-h)',
      }}
    >
      {/* HEADER */}
      <div style={{ marginBottom: '20px' }}>
        <div
          style={{
            fontSize: '12px',
            letterSpacing: '2px',
            color: '#38bdf8',
            fontWeight: 700,
            marginBottom: '8px',
          }}
        >
          INTELLIWATCH / HARDWARE LAB
        </div>

        <h1 style={{ fontSize: '28px', marginBottom: '8px' }}>
          3D Sensor Explorer
        </h1>

        <p style={{ color: 'var(--text)', fontSize: '14px' }}>
          Build and explore your IntelliWatch hardware arrangement
          inside an interactive 3D electronics workspace.
        </p>
      </div>

      {/* WORKSPACE TOOLBAR */}
      <section
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '9px',
          alignItems: 'center',
          marginBottom: '12px',
        }}
      >
        <button
          style={undoStack.length ? buttonStyle : disabledButtonStyle}
          disabled={!undoStack.length}
          onClick={handleUndo}
        >
          ↶ Undo
        </button>

        <button
          style={redoStack.length ? buttonStyle : disabledButtonStyle}
          disabled={!redoStack.length}
          onClick={handleRedo}
        >
          ↷ Redo
        </button>

        <button
          style={selectedInstanceId ? buttonStyle : disabledButtonStyle}
          disabled={!selectedInstanceId}
          onClick={handleMove}
        >
          {movingInstanceId ? 'Cancel Move' : '↔ Move'}
        </button>

        <button
          style={selectedInstanceId ? buttonStyle : disabledButtonStyle}
          disabled={!selectedInstanceId}
          onClick={() => handleRotate(-1)}
        >
          ↶ Rotate Left
        </button>

        <button
          style={selectedInstanceId ? buttonStyle : disabledButtonStyle}
          disabled={!selectedInstanceId}
          onClick={() => handleRotate(1)}
        >
          ↷ Rotate Right
        </button>

        <button
          style={selectedInstanceId ? buttonStyle : disabledButtonStyle}
          disabled={!selectedInstanceId}
          onClick={handleRemove}
        >
          ✕ Remove
        </button>

        <button
          style={buttonStyle}
          onClick={handleDeselect}
        >
          Deselect
        </button>

        <button
          style={placedComponents.length ? buttonStyle : disabledButtonStyle}
          disabled={!placedComponents.length}
          onClick={handleClear}
        >
          Clear Workspace
        </button>
      </section>

      {/* CURRENT INSTRUCTION */}
      <div
        style={{
          padding: '11px 14px',
          borderRadius: '9px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          fontSize: '12px',
          marginBottom: '12px',
        }}
      >
        {movingInstanceId
          ? 'Move mode: click a new position on the workbench to reposition the selected component.'
          : pendingComponentId
            ? `Placement mode: click the workbench to place ${selectedComponent?.name || 'the component'}.`
            : selectedInstance
              ? `Selected: ${selectedInstance.name}. Use Move, Rotate or Remove to edit it.`
              : 'Choose a component below, drag it into the workbench, or select a placed component to edit it.'}
      </div>

      {/* 3D WORKSPACE */}
      <section>
        <div
          style={{
            height: '560px',
            width: '100%',
            overflow: 'hidden',
            borderRadius: '16px',
            border: '1px solid var(--border)',
            background: '#101820',
            position: 'relative',
          }}
        >
          <Canvas
            shadows
            camera={{
              position: CAMERA_VIEWS.default,
              fov: 45,
            }}
            dpr={[1, 2]}
          >
            <Workspace
              placedComponents={placedComponents}
              selectedInstanceId={selectedInstanceId}
              onSelect={handleSelectModel}
              onPlaceAt={handlePlaceAt}
              onDeselect={handleDeselect}
              onDropComponent={handleDropComponent}
              cameraView={cameraView}
            />
          </Canvas>

          {/* CAMERA PRESETS */}
          <div
            style={{
              position: 'absolute',
              top: '14px',
              left: '14px',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px',
              maxWidth: '75%',
            }}
          >
            {[
              ['default', '3D'],
              ['front', 'Front'],
              ['back', 'Back'],
              ['left', 'Left'],
              ['right', 'Right'],
              ['top', 'Top'],
              ['bottom', 'Bottom'],
            ].map(([view, label]) => (
              <button
                key={view}
                style={{
                  ...cameraButtonStyle,
                  background: cameraView === view ? '#0369a1' : 'rgba(10,18,28,0.92)',
                }}
                onClick={() => setCameraView(view)}
              >
                {label}
              </button>
            ))}
          </div>

          {/* WORKSPACE STATUS */}
          <div
            style={{
              position: 'absolute',
              right: '14px',
              top: '14px',
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'rgba(10,18,28,0.9)',
              color: '#7dd3fc',
              fontSize: '12px',
              pointerEvents: 'none',
            }}
          >
            {placedComponents.length} / 8 Components Placed
          </div>

          {/* INSTRUCTIONS */}
          <div
            style={{
              position: 'absolute',
              left: '14px',
              bottom: '14px',
              padding: '10px 13px',
              borderRadius: '8px',
              background: 'rgba(10,18,28,0.9)',
              color: '#dbeafe',
              fontSize: '11px',
              lineHeight: 1.8,
              pointerEvents: 'none',
            }}
          >
            Left drag: Rotate camera
            <br />
            Scroll: Zoom
            <br />
            Right drag: Pan
          </div>
        </div>
      </section>

      {/* COMPONENT PANEL */}
      <section style={{ marginTop: '28px' }}>
        <div style={{ marginBottom: '16px' }}>
          <h2 style={{ fontSize: '21px', marginBottom: '6px' }}>
            Component Explorer
          </h2>

          <p style={{ fontSize: '13px', color: 'var(--text)' }}>
            Drag a component into the workbench or click a card and
            then click the desired position in the workspace.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
            gap: '14px',
          }}
        >
          {COMPONENTS.map(component => (
            <button
              key={component.id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.setData('text/plain', component.id)
                event.dataTransfer.effectAllowed = 'copy'
              }}
              onClick={() => handleChooseComponent(component.id)}
              style={{
                textAlign: 'left',
                padding: '16px',
                borderRadius: '12px',
                border: pendingComponentId === component.id
                  ? '2px solid #38bdf8'
                  : '1px solid var(--border)',
                background: pendingComponentId === component.id
                  ? 'var(--bg-card2)'
                  : 'var(--bg-card)',
                color: 'var(--text-h)',
                cursor: 'grab',
                minHeight: '100px',
              }}
            >
              <div
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: component.color,
                  marginBottom: '12px',
                }}
              />

              <div style={{ fontSize: '14px', fontWeight: 700 }}>
                {component.name}
              </div>

              <div
                style={{
                  fontSize: '11px',
                  color: 'var(--text)',
                  marginTop: '5px',
                }}
              >
                {component.category}
              </div>

              <div
                style={{
                  fontSize: '10px',
                  color: '#38bdf8',
                  marginTop: '9px',
                }}
              >
                Drag or click to add
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* SELECTED COMPONENT DETAILS */}
      {selectedComponent && (
        <section
          style={{
            marginTop: '24px',
            padding: '22px',
            borderRadius: '14px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
          }}
        >
          <div
            style={{
              fontSize: '11px',
              letterSpacing: '1.5px',
              color: '#38bdf8',
              fontWeight: 700,
              marginBottom: '8px',
            }}
          >
            {selectedInstance ? 'SELECTED HARDWARE' : 'COMPONENT INFORMATION'}
          </div>

          <h2 style={{ fontSize: '22px', marginBottom: '6px' }}>
            {selectedComponent.name}
          </h2>

          <p
            style={{
              fontSize: '12px',
              color: 'var(--text)',
              marginBottom: '14px',
            }}
          >
            {selectedComponent.category}
          </p>

          <p
            style={{
              fontSize: '14px',
              lineHeight: 1.7,
              color: 'var(--text)',
            }}
          >
            {selectedComponent.purpose}
          </p>

          <h3 style={{ fontSize: '14px', marginTop: '20px', marginBottom: '10px' }}>
            Important Pins / Connections
          </h3>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {selectedComponent.pins.map(pin => (
              <span
                key={pin}
                style={{
                  padding: '7px 11px',
                  borderRadius: '7px',
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  fontSize: '12px',
                }}
              >
                {pin}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* SAFETY AND MODEL DISCLAIMER */}
      <p
        style={{
          marginTop: '18px',
          fontSize: '11px',
          color: 'var(--text)',
          lineHeight: 1.7,
        }}
      >
        Educational 3D representations. Component dimensions and pin
        layouts are illustrative, not manufacturing-accurate CAD models.
        This workspace is a visual arrangement tool; it does not yet
        simulate electrical connections or validate circuits.
      </p>
    </main>
  )
}
