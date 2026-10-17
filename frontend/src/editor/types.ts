// The agent and the UI speak the same op language; see Editor.applyOps.

export type TextAlign = 'left' | 'center' | 'right'

export type Op =
  | {
      op: 'add_text'
      id?: string
      text: string
      x: number
      y: number
      width?: number
      fontSize?: number
      fontFamily?: string
      fontWeight?: 'bold' | 'normal' | string
      fill?: string
      textAlign?: TextAlign
    }
  | {
      op: 'add_image'
      id?: string
      src?: string
      prompt?: string
      transparent?: boolean
      x: number
      y: number
      width: number
      height: number
    }
  | {
      op: 'add_shape'
      id?: string
      shape: 'rect' | 'circle'
      x: number
      y: number
      width: number
      height: number
      fill?: string
      radius?: number
    }
  | { op: 'update'; id: string; props: Partial<ElementProps> }
  | { op: 'delete'; id: string }
  | { op: 'reorder'; id: string; to: 'front' | 'back' | 'forward' | 'backward' }
  | { op: 'set_background'; color: string }

export interface ElementProps {
  x: number
  y: number
  width: number
  height: number
  text: string
  fill: string
  fontSize: number
  fontFamily: string
  fontWeight: string
  textAlign: TextAlign
  opacity: number
}

/** Compact view of one layer, sent to the agent and shown in the layers panel. */
export interface ElementSummary {
  id: string
  type: 'text' | 'image' | 'rect' | 'circle' | 'other'
  name: string
  x: number
  y: number
  width: number
  height: number
  text?: string
  fill?: string
  fontSize?: number
  fontWeight?: string
  src?: string
  visible: boolean
  locked: boolean
}

export interface CanvasSummary {
  width: number
  height: number
  background: string
  elements: ElementSummary[]
}
