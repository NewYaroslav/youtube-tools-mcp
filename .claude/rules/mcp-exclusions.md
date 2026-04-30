# MCP Stack Configuration

## Document Lookup
Primary: context7 (query-docs) | Fallback: tavily (search)

## Web Content
Primary: fetch (fetch_markdown/fetch_txt) | Fallback: tavily (extract)

## Repo Operations
Primary: github (issues, PRs, files) | Fallback: gh CLI via Bash

## Code Analysis
Primary: serena (symbol search, references, navigation) | Fallback: Grep/Glob

## LSP
pyright-lsp: always available, no exclusion
