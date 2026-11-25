#!/usr/bin/env python3
"""Inspect existing Codex sidebar metadata. No file, account, or database writes."""
import argparse
import json
import os
from pathlib import Path
import sqlite3


def database_summary(path, tables):
    if not path.is_file():
        return {'present': False}
    result = {'present': True, 'bytes': path.stat().st_size}
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            connection.execute('PRAGMA query_only=ON')
            existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            result['rows'] = {}
            for table in tables:
                if table in existing:
                    result['rows'][table] = connection.execute('SELECT count(*) FROM ' + table).fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error as error:
        result['error'] = str(error)
    return result


def inspect(home, details=False):
    state_path = home / '.codex-global-state.json'
    result = {'codex_home': str(home), 'global_state_present': state_path.is_file(), 'read_only': True}
    state = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text())
            if not isinstance(state, dict):
                raise ValueError('Global state must be a JSON object')
        except (ValueError, OSError) as error:
            result['global_state_error'] = str(error)
            return result
    projects = state.get('local-projects', {})
    if not isinstance(projects, dict):
        result['global_state_error'] = 'Unrecognized local-projects schema; do not treat as empty'
        return result
    result['projects'] = [
        {'id': key, 'name': value.get('name'), 'root_paths': value.get('rootPaths', [])}
        for key, value in projects.items() if isinstance(value, dict)
    ]
    current = state.get('electron-renderer-content-owner')
    result['owner_views'] = []
    for key, atoms in state.items():
        if not key.startswith('electron-owner-atoms:') or not isinstance(atoms, dict):
            continue
        view = {'is_current': key == 'electron-owner-atoms:' + str(current), 'sections': []}
        scopes = atoms.get('sidebar-custom-sections-v3', {})
        if isinstance(scopes, dict):
            for scope in scopes.values():
                if not isinstance(scope, dict):
                    continue
                collapsed = set(scope.get('collapsedSectionIds', []))
                for section in scope.get('sections', []):
                    item = {'id': section.get('id'), 'name': section.get('name'),
                            'collapsed': section.get('id') in collapsed,
                            'members': len(section.get('itemKeys', []))}
                    if details:
                        item['item_keys'] = section.get('itemKeys', [])
                    view['sections'].append(item)
        descriptions = atoms.get('thread-descriptions-v1', {})
        view['description_cache_count'] = len(descriptions) if isinstance(descriptions, dict) else None
        result['owner_views'].append(view)
    assignments = state.get('thread-project-assignments', {})
    independent = state.get('projectless-thread-ids', [])
    result['saved_assignment_count'] = len(assignments)
    result['explicit_projectless_count'] = len(independent)
    if details:
        result['saved_assignments'] = assignments
        result['explicit_projectless_thread_ids'] = independent
        result['pinned_thread_ids'] = state.get('pinned-thread-ids', [])
    result['databases'] = {
        'state_5.sqlite': database_summary(home / 'state_5.sqlite', ['threads', 'projects']),
        'thread_history_1.sqlite': database_summary(home / 'thread_history_1.sqlite', ['thread_turns', 'thread_items']),
    }
    result['session_index_present'] = (home / 'session_index.jsonl').is_file()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME') or str(Path.home() / '.codex')))
    parser.add_argument('--details', action='store_true', help='Include existing project assignments and section member IDs, never message bodies or credentials')
    args = parser.parse_args()
    result = inspect(args.codex_home.expanduser(), args.details)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('global_state_error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
