#!/usr/bin/env node
// Reuse the installed SDK and local launcher. Never read or pass credentials.
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const usage = `Usage:
  node mcp_call.mjs list-tools [--tool NAME]
  node mcp_call.mjs call NAME [--args-json '{}' | --args-file /path/args.json]

Calls execute real Yuque operations. No dry-run or automatic retry.
Outputs the full MCP result as JSON; exits nonzero for tool or transport errors.`;

async function main() {
  const [mode, ...argv] = process.argv.slice(2);
  if (!mode || mode === '--help' || mode === '-h') {
    console.log(usage);
    return;
  }
  let name;
  let source;
  let sourceType;
  if (mode === 'call') name = argv.shift();
  if (!['call', 'list-tools'].includes(mode) || (mode === 'call' && (!name || name.startsWith('--')))) {
    throw new Error(usage);
  }
  while (argv.length) {
    const flag = argv.shift();
    const value = argv.shift();
    if (value === undefined) throw new Error(`Missing value for ${flag}`);
    if (mode === 'list-tools' && flag === '--tool' && name === undefined) {
      name = value;
    } else if (mode === 'call' && ['--args-json', '--args-file'].includes(flag) && source === undefined) {
      sourceType = flag;
      source = value;
    } else {
      throw new Error('Unknown or duplicate option. Use --help.');
    }
  }
  let args = {};
  if (source !== undefined) {
    const text = sourceType === '--args-file' ? await readFile(source, 'utf8') : source;
    try {
      args = JSON.parse(text);
    } catch {
      throw new Error('Arguments must be valid JSON.');
    }
    if (!args || Array.isArray(args) || typeof args !== 'object') {
      throw new Error('Arguments must be a JSON object.');
    }
  }

  const root = join(homedir(), '.config', 'yuque');
  const require = createRequire(join(root, 'runtime', 'package.json'));
  const { Client } = await import(pathToFileURL(require.resolve('@modelcontextprotocol/sdk/client/index.js')));
  const { StdioClientTransport } = await import(pathToFileURL(require.resolve('@modelcontextprotocol/sdk/client/stdio.js')));
  const client = new Client({ name: 'yuque-local-skill', version: '1.0.0' }, { capabilities: {} });
  const transport = new StdioClientTransport({ command: join(root, 'bin', 'yuque-mcp'), stderr: 'ignore' });
  let dispatchingCall = false;
  try {
    await client.connect(transport, { timeout: 30000 });
    let result;
    if (mode === 'list-tools') {
      result = await client.listTools({}, { timeout: 30000 });
      if (name) {
        result = { tools: result.tools.filter(tool => tool.name === name) };
        if (!result.tools.length) throw new Error('Requested tool was not found.');
      }
    } else {
      dispatchingCall = true;
      result = await client.callTool({ name, arguments: args }, undefined, { timeout: 30000 });
      if (result.isError) process.exitCode = 1;
    }
    console.log(JSON.stringify(result, null, 2));
  } catch {
    throw new Error(dispatchingCall
      ? 'MCP call did not complete. If it was a write, verify remote state before retrying.'
      : 'Local MCP connection or schema query failed. Check the launcher and setup.');
  } finally {
    await client.close().catch(() => {});
    await transport.close().catch(() => {});
  }
}

main().catch(error => {
  // Do not dump SDK/process error objects, environment, or credential details.
  console.error(error.code ? 'Local dependency or argument file is unavailable.' : error.message);
  process.exitCode = 1;
});
