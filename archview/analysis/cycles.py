"""Find import cycles: strongly connected components of the module graph."""

from __future__ import annotations


def _tarjan(adj: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Tarjan — no recursion limit issues on long import chains."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []
    counter = 0

    for root in adj:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(adj.get(root, ())))]
        while work:
            node, it = work[-1]
            descended = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(adj.get(nxt, ()))))
                    descended = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if descended:
                continue
            work.pop()
            if low[node] == index[node]:
                scc = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    scc.append(top)
                    if top == node:
                        break
                sccs.append(scc)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return sccs


def find_cycles(edges: list[tuple[str, str]]) -> tuple[set[str], set[tuple[str, str]]]:
    """Return (nodes_in_cycle, edges_in_cycle) for (importer, dep) pairs.

    A module is in a cycle when its strongly connected component has more
    than one member; an edge is in a cycle when both ends share an SCC.
    """
    adj: dict[str, list[str]] = {}
    for src, dst in edges:
        adj.setdefault(src, []).append(dst)
    comp: dict[str, int] = {}
    cycle_nodes: set[str] = set()
    for i, scc in enumerate(_tarjan(adj)):
        for n in scc:
            comp[n] = i
        if len(scc) > 1:
            cycle_nodes.update(scc)
    cycle_edges = {
        (s, d)
        for s, d in edges
        if s in cycle_nodes and d in cycle_nodes and comp[s] == comp[d]
    }
    return cycle_nodes, cycle_edges
