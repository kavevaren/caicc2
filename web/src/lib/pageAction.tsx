/**
 * Page action slot (redesign §2): each page registers its primary header
 * action ("+ Proyek baru", "+ Agenda baru", "Ajukan pertanyaan") and the
 * shell renders it in the header row, left of the language switch.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const SetterCtx = createContext<(n: ReactNode) => void>(() => {});
const NodeCtx = createContext<ReactNode>(null);

export function usePageActionSetter(): (n: ReactNode) => void {
  return useContext(SetterCtx);
}

/** The action node registered by the mounted page (null when none). */
export function usePageActionNode(): ReactNode {
  return useContext(NodeCtx);
}

/** Register `node` as the header action while the component is mounted. */
export function usePageAction(node: ReactNode): void {
  const set = usePageActionSetter();
  useEffect(() => {
    set(node);
    return () => set(null);
  }, [node, set]);
}

export function PageActionProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<ReactNode>(null);
  return (
    <SetterCtx.Provider value={setNode}>
      <NodeCtx.Provider value={node}>{children}</NodeCtx.Provider>
    </SetterCtx.Provider>
  );
}
