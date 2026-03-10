import { useRef, useState, useCallback, useEffect, type ReactNode } from 'react'

interface ResizableColumnsProps {
  left: ReactNode
  center: ReactNode
  right: ReactNode
  /** Initial width of left column in pixels */
  initialLeftWidth?: number
  /** Initial width of right column in pixels */
  initialRightWidth?: number
  /** Minimum width of left column in pixels */
  minLeftWidth?: number
  /** Minimum width of right column in pixels */
  minRightWidth?: number
  /** Minimum width of center column in pixels */
  minCenterWidth?: number
}

export function ResizableColumns({
  left,
  center,
  right,
  initialLeftWidth = 280,
  initialRightWidth = 240,
  minLeftWidth = 200,
  minRightWidth = 160,
  minCenterWidth = 480,
}: ResizableColumnsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [leftWidth, setLeftWidth] = useState(initialLeftWidth)
  const [rightWidth, setRightWidth] = useState(initialRightWidth)
  const dragging = useRef<'left' | 'right' | null>(null)
  const startX = useRef(0)
  const startWidth = useRef(0)

  const onPointerDown = useCallback(
    (handle: 'left' | 'right', e: React.PointerEvent) => {
      e.preventDefault()
      dragging.current = handle
      startX.current = e.clientX
      startWidth.current = handle === 'left' ? leftWidth : rightWidth
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    },
    [leftWidth, rightWidth],
  )

  useEffect(() => {
    const onPointerMove = (e: PointerEvent) => {
      if (!dragging.current || !containerRef.current) return
      const containerWidth = containerRef.current.offsetWidth
      const delta = e.clientX - startX.current

      if (dragging.current === 'left') {
        const newLeft = Math.max(minLeftWidth, startWidth.current + delta)
        const maxLeft = containerWidth - rightWidth - minCenterWidth - 8 // 8 = 2 handles × 4px
        setLeftWidth(Math.min(newLeft, maxLeft))
      } else {
        const newRight = Math.max(minRightWidth, startWidth.current - delta)
        const maxRight = containerWidth - leftWidth - minCenterWidth - 8
        setRightWidth(Math.min(newRight, maxRight))
      }
    }

    const onPointerUp = () => {
      dragging.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    }
  }, [leftWidth, rightWidth, minLeftWidth, minRightWidth, minCenterWidth])

  return (
    <div ref={containerRef} className="flex-1 flex overflow-hidden">
      {/* Left column */}
      <div className="overflow-y-auto shrink-0" style={{ width: leftWidth }}>
        {left}
      </div>

      {/* Left resize handle */}
      <div
        className="w-1 shrink-0 bg-border-subtle hover:bg-accent-color active:bg-accent-color transition-colors cursor-col-resize"
        onPointerDown={(e) => onPointerDown('left', e)}
      />

      {/* Center column */}
      <div className="flex-1 overflow-y-auto border-x border-border-subtle min-w-0">
        {center}
      </div>

      {/* Right resize handle */}
      <div
        className="w-1 shrink-0 bg-border-subtle hover:bg-accent-color active:bg-accent-color transition-colors cursor-col-resize"
        onPointerDown={(e) => onPointerDown('right', e)}
      />

      {/* Right column */}
      <div className="overflow-y-auto shrink-0" style={{ width: rightWidth }}>
        {right}
      </div>
    </div>
  )
}
