// The AI nodes' last runs, from studio/nodes.json (docs/STUDIO.md D11), loaded when an AI node is chosen on the map.
// What a node decided, by whom, and where its router sent each subject; the page computes nothing of it.
import { useEffect, useState } from 'react'
import { script } from '../../data/load'

export interface NodeRoute { decision: string; to: string; when: { en: string; ar: string }; subjects: number }
export interface NodeRun {
  id: string
  title: { en: string; ar: string }
  state: 'decided' | 'rules_only' | 'failed' | 'not_run'
  method: 'model' | 'rules' | null
  assistant: string | null
  model: string | null
  at: string | null
  cached: boolean
  seconds?: number | null
  cost_usd?: number | null
  why: string | null
  routes: NodeRoute[]
  decisions: { open_questions: unknown[] }[]
  dropped: unknown[]
}
interface NodesSection { nodes: NodeRun[]; sinks: { id: string; title: { en: string; ar: string } }[] }
export type NodeRuns = { runs: Map<string, NodeRun>; sinks: Map<string, { en: string; ar: string }> }

const read = (): NodeRuns | null => {
  const body = window.EAOS_STUDIO?.nodes as NodesSection | undefined
  if (!body) return null
  return { runs: new Map(body.nodes.map((n) => [n.id, n])), sinks: new Map(body.sinks.map((s) => [s.id, s.title])) }
}

/** The section once loaded; null while it loads, and also when this check has none (the panel is then left out). */
export function useNodeRuns(wanted: boolean): { state: 'loading' | 'absent' | 'ready'; nodes: NodeRuns | null } {
  const [nodes, setNodes] = useState<NodeRuns | null>(read)
  const [state, setState] = useState<'loading' | 'absent' | 'ready'>(nodes ? 'ready' : 'loading')
  useEffect(() => {
    if (!wanted || nodes) return
    let live = true
    script('nodes').then(() => {
      if (!live) return
      const loaded = read()
      setNodes(loaded)
      setState(loaded ? 'ready' : 'absent')
    })
    return () => { live = false }
  }, [wanted, nodes])
  return { state, nodes }
}
