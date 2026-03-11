import { useRef, useState, useCallback, useEffect, type ReactNode } from 'react'

interface ResizableColumnsProps {
  left: ReactNode
  center: ReactNode
  right: ReactNode
  overlayContent?: ReactNode
  focusLeftPanel?: boolean
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
  overlayContent,
  focusLeftPanel = false,
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
  const preFocusWidths = useRef<{ left: number; right: number } | null>(null)

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

  useEffect(() => {
    if (!containerRef.current) return

    const containerWidth = containerRef.current.offsetWidth
    const maxLeft = containerWidth - minRightWidth - minCenterWidth - 8
    const preferredLeft = Math.min(Math.max(520, Math.floor(containerWidth * 0.55)), maxLeft)

    if (focusLeftPanel) {
      if (!preFocusWidths.current) {
        preFocusWidths.current = { left: leftWidth, right: rightWidth }
      }
      setLeftWidth((current) => Math.min(Math.max(current, preferredLeft), maxLeft))
      setRightWidth(minRightWidth)
      return
    }

    if (preFocusWidths.current) {
      const { left, right } = preFocusWidths.current
      setLeftWidth(left)
      setRightWidth(right)
      preFocusWidths.current = null
    }
  }, [focusLeftPanel, leftWidth, rightWidth, minCenterWidth, minRightWidth])

  return (
    <div ref={containerRef} className="relative flex-1 flex overflow-hidden">
      {/* Left column */}
      <div className="overflow-y-auto shrink-0 transition-[width] duration-200 ease-out" style={{ width: leftWidth }}>
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
      <div className="overflow-y-auto shrink-0 transition-[width] duration-200 ease-out" style={{ width: rightWidth }}>
        {right}
      </div>

      {overlayContent && (
        <div className="absolute inset-y-0 right-0 z-20 flex items-center justify-center bg-bg-base/70 backdrop-blur-[2px]" style={{ left: leftWidth + 4 }}>
          <div className="mx-6 max-w-md rounded-lg border border-accent-border bg-bg-surface/95 px-5 py-4 text-center shadow-2xl">
            {overlayContent}
          </div>
        </div>
      )}
    </div>
  )
}
