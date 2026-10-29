# 🧩 mcp-agent-host

Partea **cealaltă** a MCP: nu serverul, ci **host-ul**, adică ce fac Claude Desktop sau Claude Code când vorbesc cu un server MCP.
Scris de mână, fără framework de agenți, ca să se vadă fiecare pas:

```
servers.json ─▶ pornește serverele pe stdio ─▶ tools/list (cu paginare)
                                              └▶ tool-uri pentru Claude (nume prefixate, JSON Schema)
utilizator ─▶ Claude ─▶ tool_use ─▶ politică: read-only? rulează : cere aprobare
                                  └▶ tools/call ─▶ <tool_output>…</tool_output> ─▶ Claude ─▶ … ─▶ răspuns
```

> Pasul 4 din planul meu de studiu: „agent loop scris de mână” și „MCP: tools, JSON-RPC, transport stdio”.
> Completează [`technova-mcp-server`](https://github.com/cs1lyuha/technova-mcp-server), care e partea de server.

![CI](https://github.com/cs1lyuha/mcp-agent-host/actions/workflows/ci.yml/badge.svg)

## Demo (fără cheie API)

`python -m host demo` pornește serverul de exemplu ca **proces separat pe stdio**, iar un model scriptat încearcă să „curețe notițele expirate”:

```
🔌 notes: search_notes, delete_note*
   (* = cere aprobare)

⚠️  aprobare cerută pentru notes__delete_note {'note_id': 'promo-vechi'} → DA
· tool_ok    notes__search_notes    promo-vechi: Promoția de vară (expirată în august).
· tool_ok    notes__delete_note     notița promo-vechi a fost ștearsă
· final                             Am șters notița expirată.
```

Cu `--deny`, operatorul refuză. Modelul primește refuzul ca `tool_result` cu `is_error` și explică:

```
· denied     notes__delete_note     {'note_id': 'promo-vechi'}
agent › Operatorul nu a aprobat ștergerea; notița rămâne.
```

Chat real cu Claude, peste orice servere MCP:

```bash
export ANTHROPIC_API_KEY=...
python -m host chat --config examples/servers.json
```

Config-ul are același format ca la Claude Desktop, deci se poate folosi și cu `technova-mcp-server`:

```json
{"mcpServers": {"technova": {"command": "technova-mcp", "args": ["serve"], "env": {"TECHNOVA_TOKEN": "tn_..."}}}}
```

## Ce garantează bucla (indiferent ce decide modelul)

| Garanție | Cum | Test |
|---|---|---|
| un tool care scrie nu rulează fără om | doar tool-urile cu `readOnlyHint: true` rulează direct; restul trec prin `approver` | `test_destructive_tool_denied_by_default` |
| un server fără adnotări nu e crezut pe cuvânt | lipsa adnotării = „poate scrie” | `test_discovery_annotations_and_schema` |
| refuzul nu blochează conversația | refuzul ajunge la model ca eroare de tool, iar modelul explică | `test_destructive_tool_denied_by_default` |
| un model care se învârte în cerc se oprește | bugete pentru pași, apeluri de tool-uri și tokeni de output; oprire curată, cu mesaj | `test_max_steps_*`, `test_max_tool_calls`, `test_output_token_budget` |
| apelurile paralele rămân paralele | toate `tool_result`-urile unui pas într-un singur mesaj `user` | `test_parallel_calls_one_user_message` |
| un rezultat uriaș nu umple contextul | trunchiere la 8000 de caractere, cu mențiune explicită | `test_call_ok_error_unknown_and_truncation` |
| textul din tool-uri nu e luat drept instrucțiune | încadrat în `<tool_output>`, iar system prompt-ul spune că e doar date | `test_read_only_tool_runs_without_approval` |
| istoricul nu se rescrie | conținutul asistentului se trimite înapoi exact cum a venit (inclusiv thinking) | `test_history_is_append_only_across_questions` |
| două servere cu tool-uri cu același nume | nume prefixate `server__tool`, curățate după regula API-ului | `test_safe_names` |

## Structura

| Fișier | Rol |
|---|---|
| `host/bridge.py` | descoperire de tool-uri, traducere pentru model, execuție prin `tools/call`, trunchiere |
| `host/agent.py` | bucla de agent, politica de aprobare, bugetele, evenimentele |
| `host/brains.py` | `ClaudeBrain` (API Anthropic, async) și `ScriptedBrain` pentru teste |
| `host/__main__.py` | `demo` și `chat`, config în format Claude Desktop, aprobare în terminal |
| `examples/notes_server.py` | server MCP de exemplu (stdio) |

**15 teste:** `pytest -q`. Testele cu `Client(server)` folosesc protocolul MCP real, în memorie. `test_cli_stdio.py` pornește serverul ca proces separat.

## De ce de mână și nu cu un framework?

Ca să pot răspunde la întrebările de interviu „ce se întâmplă între model și tool?” și „cum oprești un agent să facă o acțiune greșită?”.
Răspunsul nu e „promptul îi spune să nu facă”, ci: **bucla nu execută acțiunea fără aprobare, oricât ar insista modelul.**

## Ce urmează

- [ ] Transport Streamable HTTP (servere remote, cu Bearer)
- [ ] Resurse și prompturi MCP expuse în chat (`/resources`, `/prompt support_reply`)
- [ ] Aprobare cu reguli („delete în staging: automat; în producție: om”)
- [ ] Jurnal al sesiunii, pentru audit
