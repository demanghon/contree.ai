import { Injectable } from '@angular/core';

export interface GameNode {
    id: string;
    label: string;
    player?: number;
    trick?: string[];
    score?: number;
    currentPoints?: { ns: number, ew: number };
    hands?: string[][]; // For root node
    trump?: string;
    children: GameEdge[];
}

export interface GameEdge {
    to: string; // ID of the target node
    node?: GameNode; // Direct reference
    card: string;
    score?: number;
}

@Injectable({
    providedIn: 'root'
})
export class DotParserService {

    parse(dotContent: string): GameNode | null {
        const lines = dotContent.split('\n');
        const nodes = new Map<string, GameNode>();
        const edges: { from: string, to: string, label: string }[] = [];
        let rootId: string | null = null;

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('digraph') || trimmed.startsWith('}') || trimmed.startsWith('node')) {
                continue;
            }

            // Edge: 123 -> 456 [label="..."]
            if (trimmed.includes('->')) {
                const parts = trimmed.split('->');
                const from = parts[0].trim();
                const rest = parts[1].trim();
                const to = rest.split('[')[0].trim();
                const labelMatch = rest.match(/label="([^"]+)"/);
                const label = labelMatch ? labelMatch[1] : '';

                edges.push({ from, to, label });
            }
            // Node: 123 [label="..."]
            else if (trimmed.includes('[label=')) {
                const parts = trimmed.split('[');
                const id = parts[0].trim();
                const labelMatch = trimmed.match(/label="([^"]+)"/);
                let label = labelMatch ? labelMatch[1] : '';

                // Unescape newlines
                label = label.replace(/\\n/g, '\n');

                const node: GameNode = {
                    id,
                    label,
                    children: []
                };

                this.parseNodeLabel(node, label);
                nodes.set(id, node);

                if (label.startsWith('ROOT')) {
                    rootId = id;
                }
            }
        }

        if (!rootId) return null;

        // Build Tree
        for (const edge of edges) {
            const parent = nodes.get(edge.from);
            const child = nodes.get(edge.to);
            if (parent && child) {
                // Parse edge label: "7D (116)" or "7D"
                let card = edge.label;
                let score = undefined;
                if (card.includes('(')) {
                    const parts = card.split('(');
                    card = parts[0].trim();
                    score = parseInt(parts[1].replace(')', ''));
                }

                parent.children.push({
                    to: edge.to,
                    node: child,
                    card,
                    score
                });
            }
        }

        return nodes.get(rootId) || null;
    }

    private parseNodeLabel(node: GameNode, label: string) {
        const lines = label.split('\n');
        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (line.startsWith('Player:')) {
                node.player = parseInt(line.split(':')[1].trim());
            } else if (line.startsWith('Score:')) {
                const s = line.split(':')[1].trim();
                if (s !== '?') node.score = parseInt(s);
            } else if (line.startsWith('Points:')) {
                // Points: NS=10, EW=20
                try {
                    const parts = line.split(':')[1].split(',');
                    const nsPart = parts[0].split('=')[1];
                    const ewPart = parts[1].split('=')[1];
                    if (nsPart && ewPart) {
                        const ns = parseInt(nsPart.trim());
                        const ew = parseInt(ewPart.trim());
                        node.currentPoints = { ns, ew };
                    }
                } catch (e) {
                    console.warn('Failed to parse points:', line);
                }
            } else if (line.startsWith('Trump:')) {
                node.trump = line.split(':')[1].replace(/\\/g, '').trim();
            } else if (line.startsWith('Trick:')) {
                const content = line.substring(line.indexOf(':') + 1).replace(/\\/g, '').trim();
                if (content !== 'Empty') {
                    // P0:7D, P1:8H
                    node.trick = content.split(',').map(s => s.trim());
                } else {
                    node.trick = [];
                }
            } else if (line.startsWith('P') && line.includes(':')) {
                // Hand: P0: 7D 8D ...
                if (!node.hands) node.hands = [[], [], [], []];
                const pIndex = parseInt(line.charAt(1));
                const content = line.split(':')[1].replace(/\\/g, '').trim();
                if (content !== 'Empty') {
                    node.hands[pIndex] = content.split(' ');
                }
            }
        }
    }
}
