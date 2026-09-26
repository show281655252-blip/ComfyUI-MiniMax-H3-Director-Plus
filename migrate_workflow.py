"""Convert a saved patched Director workflow into a separate Director Plus copy."""
import argparse
import copy
import json
import uuid
from pathlib import Path

NODE_TYPES = {
    'MiniMaxH3Director': 'DirectorPlusTimeline',
    'MiniMaxH3DirectorLongVideo': 'DirectorPlusGenerate',
    'MiniMaxH3DirectorVideoOutput': 'DirectorPlusVideoOutput',
}


def convert(workflow):
    workflow = copy.deepcopy(workflow)
    count = 0
    graphs = [workflow]
    while graphs:
        graph = graphs.pop()
        graphs.extend(graph.get('definitions', {}).get('subgraphs', []))
        for node in graph.get('nodes', []):
            old = node.get('type')
            if old not in NODE_TYPES:
                continue
            node['type'] = NODE_TYPES[old]
            node.setdefault('properties', {})['Node name for S&R'] = node['type']
            for key in ['cnr_id', 'aux_id', 'ver']:
                node['properties'].pop(key, None)
            count += 1
            if old != 'MiniMaxH3Director':
                continue
            values = node.get('widgets_values', [])
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.lstrip().startswith('{'):
                    continue
                state = json.loads(value)
                if not isinstance(state, dict) or 'long_video' not in state:
                    continue
                long = state['long_video']
                long.update(project_id=str(uuid.uuid4()), source_mode_enabled=False, start_mode='new')
                for key in ['cache_owner', 'last_preview', 'source_video', 'source_color_strength']:
                    long.pop(key, None)
                for scene in long.get('clips', []):
                    scene['validated'] = False
                values[index] = json.dumps(state, ensure_ascii=False)
    return workflow, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists. Choose a new filename; original workflows are never overwritten.')
    result, count = convert(json.loads(args.input.read_text(encoding='utf-8-sig')))
    if not count:
        parser.error('No patched Director nodes found in this workflow.')
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(f'Converted {count} nodes. Prompts and seeds preserved; scene approvals reset for the separate cache.')


if __name__ == '__main__':
    main()
