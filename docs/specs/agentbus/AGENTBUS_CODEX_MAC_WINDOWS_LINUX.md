# AgentBus para coordinación entre Codex en Mac, Windows y servidor Linux

## 0. Objetivo del sistema

Construir un sistema local/self-hosted para que varias instancias de Codex, situadas en máquinas distintas y proyectos/carpetas distintas, puedan pedirse trabajo entre sí sin depender del cliente gráfico de Codex, sin automatización visual frágil, sin vigilancia por IA y sin consumo continuo de tokens.

El sistema debe permitir que una instancia de Codex en Windows, especializada en infraestructura/CodexIAChat, pueda pedir tareas concretas a una instancia de Codex en Mac, especializada en UI/diseño, y viceversa. La comunicación debe ser mecánica, accionable y trazable. Las IAs no deben estar refrescando chats ni leyendo conversaciones completas. Solo deben ser invocadas cuando haya una tarea real.

La solución final se basa en:

1. Servidor Linux siempre encendido como nodo central.
2. NATS como bus de eventos/wake-up sin polling caro.
3. Archivos `.md`/`.json` como contexto pesado y artefactos.
4. Workers locales en Mac y Windows.
5. Codex CLI, preferentemente `codex exec`, para ejecutar tareas frías/autocontenidas.
6. Opcionalmente MCP para una fase avanzada.
7. `AGENTS.md` y un Skill propio de Codex para imponer disciplina de coordinación.
8. Nada de automatización del cliente gráfico de Codex.

---

## 1. Decisiones arquitectónicas cerradas

### 1.1. No automatizar el cliente gráfico de Codex

No se debe usar automatización por clic, foco de ventana, pegado en la UI, AppleScript/AutoHotkey contra la interfaz gráfica ni scraping de pantallas.

Razones:

1. El cliente gráfico puede cambiar.
2. Los hilos pueden no abrirse correctamente.
3. Se puede perder tiempo depurando problemas de foco, ventanas, sesión o UI.
4. Es una dependencia frágil para una infraestructura que debe ser fiable.
5. La interfaz gráfica debe quedar para uso humano, no para orquestación.

### 1.2. Usar Codex CLI para tareas frías

La ruta principal será ejecutar Codex desde CLI, idealmente con `codex exec` o equivalente no interactivo. Cada tarea debe llegar a Codex como un paquete autocontenido con:

1. Objetivo.
2. Contexto mínimo.
3. Archivos permitidos.
4. Restricciones.
5. Salida esperada.
6. Ruta de `result.json`.
7. Instrucciones de no mirar otros hilos ni logs.

### 1.3. No depender de memoria conversacional

Las conversaciones vivas de Codex no serán la fuente de verdad. El contexto relevante debe consolidarse en archivos canónicos:

```txt
docs/current_state.md
docs/current_decisions.md
docs/current_architecture.md
docs/open_questions.md
docs/api/current_contracts.md
docs/ui/current_design_language.md
```

Codex puede trabajar en frío porque el worker le entregará un `task pack` suficiente.

### 1.4. Las IAs no vigilan

Codex no debe consultar si hay mensajes pendientes. No debe revisar periódicamente una carpeta `inbox`. No debe leer logs ni histórico salvo que una tarea concreta lo indique.

La vigilancia corresponde a procesos baratos sin IA:

1. `agentbus-server` en Linux.
2. `codex-worker-windows`.
3. `codex-worker-mac`.

Estos procesos pueden estar siempre activos sin gastar tokens.

### 1.5. Comunicación por paquetes de trabajo, no por chat

No se debe replicar un chat humano. El sistema debe transmitir `REQUEST`, `REPLY`, `HANDOFF`, `BLOCKED`, `ARTIFACT_READY`, `ERROR`, `LOCK`, `UNLOCK`, etc.

Cada mensaje debe ser estructurado, corto y con referencias a archivos de contexto.

---

## 2. Topología final

```txt
                      ┌─────────────────────────────┐
                      │       Servidor Linux         │
                      │                             │
                      │  agentbus-server             │
                      │  nats-server                 │
                      │  /srv/agentbus               │
                      │  /srv/codexiachat/coordination   │
                      │  opcional: PostgreSQL        │
                      └─────────────┬───────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │                                │
          ┌─────────▼──────────┐          ┌──────────▼─────────┐
          │ Windows Workstation │          │        Mac         │
          │                    │          │                    │
          │ CodexIAChat Infra       │          │ UI / Diseño        │
          │ Codex CLI           │          │ Codex CLI           │
          │ codex-worker-win    │          │ codex-worker-mac    │
          └────────────────────┘          └────────────────────┘
```

---

## 3. Componentes

### 3.1. `agentbus-server`

Servicio central en Linux. Puede implementarse en Rust, Go o Python. Se recomienda Rust si se quiere integrarlo a largo plazo en CodexIAChat; Python/FastAPI si se prioriza velocidad de implementación.

Responsabilidades:

1. Mantener registro de agentes.
2. Mantener registro de proyectos.
3. Recibir tareas.
4. Validar contratos JSON.
5. Guardar mensajes y resultados.
6. Publicar wake-ups en NATS.
7. Gestionar estados `pending`, `running`, `completed`, `failed`, `cancelled`, `expired`.
8. Gestionar locks de recursos.
9. Gestionar rutas de artefactos/contexto.
10. Generar task packs.
11. Exponer API HTTP local opcional.
12. Exponer MCP opcional en fase avanzada.

### 3.2. `nats-server`

Broker central de eventos. Uso principal:

1. Despertar workers.
2. Publicar notificaciones de nuevas tareas.
3. Publicar resultados.
4. Evitar polling constante.
5. Mantener un patrón event-driven.

Subjects recomendados:

```txt
agent.windows-infra.wakeup
agent.mac-ui.wakeup

agent.windows-infra.events
agent.mac-ui.events

project.codexiachat.events
project.codexiachat.errors
project.codexiachat.locks
project.codexiachat.artifacts
```

### 3.3. `codex-worker-windows`

Proceso residente en Windows.

Responsabilidades:

1. Conectar a NATS.
2. Escuchar `agent.windows-infra.wakeup`.
3. Descargar o materializar task pack.
4. Copiar tarea a `.agentbus/inbox/`.
5. Ejecutar Codex CLI en la carpeta correcta.
6. Esperar resultado.
7. Validar `result.json`.
8. Subir/publicar resultado en AgentBus.
9. Archivar task pack.
10. No usar IA salvo cuando invoca Codex para una tarea real.

### 3.4. `codex-worker-mac`

Igual que el worker de Windows, pero apuntando al proyecto/carpeta de UI/diseño.

### 3.5. Skill de Codex: `agentbus-handoff`

Skill propio para enseñar a Codex cómo procesar tareas AgentBus.

No debe vigilar. No debe despertar nada. Solo debe actuar cuando el prompt diga explícitamente que procese una tarea AgentBus.

### 3.6. `AGENTS.md`

Debe usarse para reglas permanentes:

1. Reglas globales de no polling.
2. Rol de cada proyecto.
3. Restricciones por carpeta.
4. Políticas de lectura de contexto.
5. Política de resultados.

### 3.7. MCP opcional

MCP queda como fase avanzada. No es necesario para la primera implementación funcional.

Uso futuro:

1. `agentbus_get_task`
2. `agentbus_send_reply`
3. `agentbus_create_request`
4. `agentbus_lock_resource`
5. `agentbus_release_lock`
6. `agentbus_read_context`

---

## 4. Estructura de carpetas en el servidor Linux

```txt
/srv/agentbus/
  config/
    agents.yaml
    projects.yaml
    routes.yaml
    server.yaml

  schemas/
    task.schema.json
    result.schema.json
    lock.schema.json
    agent.schema.json
    artifact.schema.json

  tasks/
    pending/
    running/
    completed/
    failed/
    cancelled/

  results/
    pending/
    completed/
    failed/

  messages/
    message_log.jsonl

  locks/
    active_locks.json
    lock_log.jsonl

  artifacts/
    codexiachat/
      ui/
      infra/
      docs/
      screenshots/
      diagrams/

  handoffs/
    codexiachat/

  logs/
    agentbus-server.log
    task_runs.jsonl
    errors.jsonl
```

Contexto del proyecto:

```txt
/srv/codexiachat/coordination/
  state/
    current_state.md
    current_decisions.md
    current_architecture.md
    open_questions.md

  handoffs/
    task_*.md

  artifacts/
    ui/
    infra/
    specs/
    screenshots/
    diagrams/

  summaries/
    windows-infra-summary.md
    mac-ui-summary.md

  registry/
    project_registry.yaml
    agent_registry.yaml
```

---

## 5. Estructura dentro de cada proyecto Codex

En Windows, por ejemplo:

```txt
C:\Projects\CodexIAChat\
  AGENTS.md
  docs/
    current_state.md
    current_decisions.md
    current_architecture.md
    api/
      current_contracts.md

  .agentbus/
    inbox/
    outbox/
    archive/
    logs/
    state/
      local_agent_state.json
```

En Mac:

```txt
/Users/example/Projects/CodexIAChatUI/
  AGENTS.md
  docs/
    current_state.md
    current_decisions.md
    ui/
      current_design_language.md

  .agentbus/
    inbox/
    outbox/
    archive/
    logs/
    state/
      local_agent_state.json
```

---

## 6. Registro de agentes

Archivo:

```txt
/srv/agentbus/config/agents.yaml
```

Ejemplo:

```yaml
agents:
  windows-infra:
    description: "Codex especializado en infraestructura, backend, CodexIAChat, workers, APIs, colas, persistencia y despliegue."
    machine: "windows"
    os: "windows"
    wake_subject: "agent.windows-infra.wakeup"
    event_subject: "agent.windows-infra.events"
    repo_path: "C:\\Projects\\CodexIAChat"
    agentbus_dir: "C:\\Projects\\CodexIAChat\\.agentbus"
    role: "infra"
    codex:
      mode: "exec"
      profile: "windows-infra"
      default_model: null
      approval_policy: "workspace-write"
      sandbox_policy: "workspace-write"
    allowed_projects:
      - "codexiachat"
    forbidden_scopes:
      - "UI redesign unless explicitly requested"
      - "Frontend visual design unless explicitly requested"

  mac-ui:
    description: "Codex especializado en UI, UX, diseño, frontend, estados visuales, componentes e interacción."
    machine: "mac"
    os: "macos"
    wake_subject: "agent.mac-ui.wakeup"
    event_subject: "agent.mac-ui.events"
    repo_path: "/Users/example/Projects/CodexIAChatUI"
    agentbus_dir: "/Users/example/Projects/CodexIAChatUI/.agentbus"
    role: "ui"
    codex:
      mode: "exec"
      profile: "mac-ui"
      default_model: null
      approval_policy: "workspace-write"
      sandbox_policy: "workspace-write"
    allowed_projects:
      - "codexiachat"
    forbidden_scopes:
      - "Backend infrastructure unless explicitly requested"
      - "API contract changes unless explicitly requested"
```

---

## 7. Registro de proyectos

Archivo:

```txt
/srv/agentbus/config/projects.yaml
```

Ejemplo:

```yaml
projects:
  codexiachat:
    name: "CodexIAChat"
    description: "Sistema de coordinación, automatización y ejecución de trabajos entre proyectos/software."
    canonical_state:
      - "/srv/codexiachat/coordination/state/current_state.md"
      - "/srv/codexiachat/coordination/state/current_decisions.md"
      - "/srv/codexiachat/coordination/state/current_architecture.md"
      - "/srv/codexiachat/coordination/state/open_questions.md"
    artifact_root: "/srv/codexiachat/coordination/artifacts"
    handoff_root: "/srv/codexiachat/coordination/handoffs"
    default_agents:
      infra: "windows-infra"
      ui: "mac-ui"
```

---

## 8. Tipos de mensaje

### 8.1. `REQUEST`

Una IA pide una tarea concreta a otra.

Uso:

1. Windows necesita una pantalla, diseño o decisión UX de Mac.
2. Mac necesita un contrato API, endpoint, estructura de datos o decisión de backend de Windows.
3. Un agente necesita validación puntual de otro.

### 8.2. `REPLY`

Respuesta a una request.

Debe incluir:

1. `correlation_id`
2. resumen
3. artefactos generados
4. preguntas abiertas
5. siguiente acción recomendada

### 8.3. `HANDOFF`

Transferencia de trabajo más amplia.

Uso:

1. Una tarea debe pasar de UI a backend.
2. Un diseño terminado debe pasar a implementación.
3. Una API terminada debe pasar a consumo por frontend.

### 8.4. `BLOCKED`

Un agente está bloqueado y necesita algo específico.

### 8.5. `ARTIFACT_READY`

Un archivo, spec, contrato, build, mockup o documento está listo.

### 8.6. `LOCK`

Reserva temporal de un recurso para evitar pisarse.

### 8.7. `UNLOCK`

Liberación de recurso.

### 8.8. `ERROR`

Error operativo o fallo de ejecución.

### 8.9. `HEARTBEAT`

Mensaje mecánico de vida del worker. No debe activar Codex.

### 8.10. `SUMMARY`

Resumen generado por sistema o por IA, normalmente no accionable salvo que se marque explícitamente.

---

## 9. Contrato JSON de tarea

Archivo:

```txt
/srv/agentbus/schemas/task.schema.json
```

Esquema conceptual:

```json
{
  "id": "task_20260528_001",
  "version": "1.0",
  "project": "codexiachat",
  "kind": "REQUEST",
  "from": "windows-infra",
  "to": "mac-ui",
  "priority": "normal",
  "summary": "Diseñar pantalla para monitorizar jobs fallidos y reintentos.",
  "why": "El backend ya tiene endpoints de retry/cancel/list, pero falta una UI clara para uso humano.",
  "known_context": [
    "Los jobs tienen estados pending, running, failed, succeeded, cancelled.",
    "Retry solo aplica a failed.",
    "Cancel solo aplica a pending/running."
  ],
  "context_refs": [
    "/srv/codexiachat/coordination/state/current_state.md",
    "/srv/codexiachat/coordination/state/current_decisions.md",
    "/srv/codexiachat/coordination/handoffs/task_20260528_001.md"
  ],
  "allowed_files": [
    "docs/ui/",
    ".agentbus/outbox/"
  ],
  "forbidden_scope": [
    "No modificar backend.",
    "No cambiar contratos API.",
    "No leer otros mensajes AgentBus."
  ],
  "expected_outputs": [
    "docs/ui/job-retry-panel.md",
    "docs/ui/job-retry-states.md",
    ".agentbus/outbox/task_20260528_001.result.json"
  ],
  "reply_to": "windows-infra",
  "ack_required": true,
  "created_at": "2026-05-28T15:30:00Z",
  "expires_at": "2026-05-29T15:30:00Z"
}
```

---

## 10. Contrato JSON de resultado

Archivo:

```txt
/srv/agentbus/schemas/result.schema.json
```

Ejemplo:

```json
{
  "task_id": "task_20260528_001",
  "version": "1.0",
  "from": "mac-ui",
  "to": "windows-infra",
  "status": "completed",
  "summary": "Se diseñó la pantalla de reintentos de jobs con estados empty/loading/error/success y acciones retry/cancel.",
  "files_created": [
    "docs/ui/job-retry-panel.md",
    "docs/ui/job-retry-states.md"
  ],
  "files_modified": [],
  "artifact_refs": [
    "/srv/codexiachat/coordination/artifacts/ui/job-retry-panel.md"
  ],
  "open_questions": [
    "Confirmar si cancel debe pedir confirmación modal o acción inline."
  ],
  "requests_created": [
    {
      "to": "windows-infra",
      "kind": "BACKEND_CONTRACT_CLARIFICATION",
      "summary": "Confirmar payload exacto de POST /jobs/{id}/retry."
    }
  ],
  "next_action": "Windows debe validar endpoints y errores posibles.",
  "completed_at": "2026-05-28T15:55:00Z"
}
```

---

## 11. Task Pack

El `task pack` es el paquete que el worker deja en el proyecto local antes de invocar Codex.

Estructura:

```txt
.agentbus/inbox/task_20260528_001/
  task.json
  task.md
  context.md
  allowed_files.txt
  expected_output.json
  previous_decisions.md
```

### 11.1. `task.md`

Debe ser legible por Codex y por humanos.

Plantilla:

```md
# AgentBus Task: task_20260528_001

## Role

You are `mac-ui`.

## Task

Design the UI screen for monitoring failed jobs and retry/cancel actions.

## Why

The backend already exposes job status and job action concepts, but the product lacks a clear user-facing workflow.

## Known context

- Jobs can be `pending`, `running`, `failed`, `succeeded`, `cancelled`.
- Retry applies only to `failed`.
- Cancel applies only to `pending` or `running`.

## Allowed context

Read only:

- `.agentbus/inbox/task_20260528_001/context.md`
- `.agentbus/inbox/task_20260528_001/previous_decisions.md`
- `docs/ui/current_design_language.md`
- `docs/current_state.md`

## Forbidden scope

- Do not modify backend.
- Do not modify API contracts.
- Do not inspect other AgentBus tasks.
- Do not poll for messages.
- Do not read historical chats.

## Expected outputs

Write:

- `docs/ui/job-retry-panel.md`
- `docs/ui/job-retry-states.md`
- `.agentbus/outbox/task_20260528_001.result.json`

## Completion rule

The task is complete only when the result JSON exists and validates against `result.schema.json`.
```

### 11.2. `context.md`

Debe contener el contexto mínimo consolidado. No debe ser una copia gigante de logs.

Estructura:

```md
# Context Pack

## Project

CodexIAChat.

## Current state

Resumen corto del estado actual.

## Relevant decisions

Lista corta de decisiones ya tomadas.

## Relevant files

- `docs/api/job-contracts.md`
- `docs/current_state.md`

## Constraints

- Mantener diseño compatible con Tauri/desktop.
- Minimizar decisiones especulativas de backend.
```

---

## 12. Worker local

### 12.1. Responsabilidades del worker

Cada worker local debe:

1. Iniciarse como servicio.
2. Conectarse al servidor Linux.
3. Suscribirse al subject NATS del agente.
4. Esperar tareas sin polling activo caro.
5. Descargar/materializar task pack.
6. Ejecutar Codex CLI en el repo correcto.
7. Validar salida.
8. Publicar resultado.
9. Registrar logs.
10. Manejar timeouts y errores.

### 12.2. Pseudoflujo

```txt
worker starts
  load config
  connect to NATS
  subscribe to wake_subject

on wakeup:
  fetch pending tasks for this agent
  for each task:
    mark task as running
    materialize task pack into repo/.agentbus/inbox/task_id/
    build codex prompt
    run codex exec in repo_path
    wait for .agentbus/outbox/task_id.result.json
    validate result
    upload artifacts/results
    mark task as completed or failed
```

### 12.3. Pseudocódigo Python

```python
def on_wakeup(message):
    tasks = agentbus.fetch_pending_tasks(agent_id="mac-ui")

    for task in tasks:
        agentbus.mark_running(task.id)

        task_dir = materialize_task_pack(task)

        prompt = f'''
Use the agentbus-handoff skill.

Process this task:
{task_dir}/task.md

Rules:
- Do not poll for messages.
- Do not inspect previous chats.
- Do not read other AgentBus tasks.
- Read only files listed in the task.
- Write the required result JSON.
'''

        result = run_codex_exec(
            cwd=AGENT_REPO_PATH,
            prompt=prompt,
            timeout_seconds=3600
        )

        result_file = wait_for_result(task.id)

        if validate_result(result_file):
            agentbus.publish_result(task.id, result_file)
            agentbus.mark_completed(task.id)
        else:
            agentbus.mark_failed(task.id, "Invalid or missing result file")
```

---

## 13. Invocación de Codex CLI

La implementación debe abstraer el comando exacto para permitir cambios de versión.

Regla de seguridad: la tarea no puede controlar el ejecutable, argumentos, entorno, directorio de trabajo, sandbox, approval policy ni política de red. Todo eso debe venir de un perfil estático de worker revisado por humanos. La tarea solo puede aportar el `task_id` y las rutas previamente validadas dentro de `.agentbus/inbox/<task_id>/`.

Configurable:

```yaml
codex:
  executable: "codex"
  mode: "exec"
  extra_args:
    - "--skip-git-repo-check"
  env:
    RUST_LOG: "info"
```

Ejemplo conceptual:

```bash
codex exec "Use the agentbus-handoff skill. Process .agentbus/inbox/task_20260528_001/task.md"
```

El worker debe capturar:

1. stdout
2. stderr
3. exit code
4. duración
5. ruta de resultado
6. archivos creados/modificados si es posible

---

## 14. Servicio en Linux

### 14.1. Instalar NATS

Instalación recomendada mediante binario oficial, paquete del sistema o Docker.

Modo simple:

```bash
sudo useradd --system --home /var/lib/nats --shell /usr/sbin/nologin nats || true
sudo mkdir -p /var/lib/nats/jetstream
sudo chown -R nats:nats /var/lib/nats
```

Archivo:

```txt
/etc/nats/nats-server.conf
```

Contenido recomendado:

```conf
server_name: agentbus-nats
host: <tailscale-or-local-bind-address>
port: 4222

jetstream {
  store_dir: /var/lib/nats/jetstream
  max_mem_store: 512Mb
  max_file_store: 10Gb
}

authorization {
  users = [
    {user: "agentbus", password: "<replace-with-agentbus-password>"},
    {user: "mac_ui", password: "<replace-with-mac-worker-password>"},
    {user: "windows_infra", password: "<replace-with-windows-worker-password>"}
  ]
}
```

Systemd:

```ini
[Unit]
Description=NATS Server for AgentBus
After=network.target

[Service]
User=nats
Group=nats
ExecStart=/usr/local/bin/nats-server -c /etc/nats/nats-server.conf
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 14.2. Servicio `agentbus-server`

Systemd:

```ini
[Unit]
Description=AgentBus Server
After=network.target nats.service
Requires=nats.service

[Service]
User=agentbus
Group=agentbus
WorkingDirectory=/srv/agentbus/server
ExecStart=/srv/agentbus/server/agentbus-server --config /srv/agentbus/config/server.yaml
Restart=always
RestartSec=3
Environment=RUST_LOG=info

[Install]
WantedBy=multi-user.target
```

---

## 15. Servicio en Windows

Opciones:

1. Windows Task Scheduler.
2. NSSM.
3. Servicio nativo si se implementa en Rust/Go.
4. Ejecución manual durante la fase inicial.

Configuración ejemplo:

```yaml
agent_id: "windows-infra"
server_url: "http://<server-linux-ip>:8088"
nats_url: "nats://<server-linux-ip>:4222"
nats_user: "windows_infra"
nats_password: "<replace-with-windows-worker-password>"
repo_path: "C:\\Projects\\CodexIAChat"
agentbus_dir: "C:\\Projects\\CodexIAChat\\.agentbus"
codex_executable: "codex"
```

Comando conceptual:

```powershell
codex-worker.exe --config C:\Projects\CodexIAChat\.agentbus\worker.windows.yaml
```

---

## 16. Servicio en Mac

Opciones:

1. `launchd`.
2. Ejecución manual.
3. Servicio gestionado por Homebrew si se empaqueta.

Configuración ejemplo:

```yaml
agent_id: "mac-ui"
server_url: "http://<server-linux-ip>:8088"
nats_url: "nats://<server-linux-ip>:4222"
nats_user: "mac_ui"
nats_password: "<replace-with-mac-worker-password>"
repo_path: "/Users/example/Projects/CodexIAChatUI"
agentbus_dir: "/Users/example/Projects/CodexIAChatUI/.agentbus"
codex_executable: "codex"
```

`launchd` plist conceptual:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>one.nucleos.agentbus.mac-ui</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/local/bin/codex-worker</string>
      <string>--config</string>
      <string>/Users/example/Projects/CodexIAChatUI/.agentbus/worker.mac.yaml</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/agentbus-mac-ui.out.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/agentbus-mac-ui.err.log</string>
  </dict>
</plist>
```

---

## 17. AGENTS.md global

Ubicación sugerida:

```txt
~/.codex/AGENTS.md
```

Contenido:

```md
# Global AgentBus Rules

Codex must never poll, refresh, monitor queues, scan AgentBus inboxes, or inspect historical chats by itself.

External workers deliver tasks. Codex only processes AgentBus tasks when a prompt explicitly points to a task file.

When processing an AgentBus task:

1. Use the `agentbus-handoff` skill if available.
2. Read only the task file and explicitly listed context files.
3. Do not inspect other `.agentbus/inbox` tasks.
4. Do not read `.agentbus/archive` unless explicitly instructed.
5. Do not read historical Codex conversations.
6. Do not modify files outside the allowed scope.
7. Write the required result JSON.
8. If another agent is needed, create an AgentBus REQUEST instead of guessing.
9. If required context is missing, mark the result as `blocked` and specify exactly what is needed.
```

---

## 18. AGENTS.md para Windows / infraestructura

Ubicación:

```txt
C:\Projects\CodexIAChat\AGENTS.md
```

Contenido:

```md
# Role: windows-infra

This Codex instance owns CodexIAChat infrastructure, backend, orchestration, workers, job execution, APIs, persistence, queues, deployment, server-side reliability, and operational tooling.

## Scope

Allowed by default:

- Backend code.
- Infrastructure code.
- Worker orchestration.
- API contracts.
- Queue/persistence logic.
- Deployment scripts.
- Operational documentation.

Forbidden unless explicitly requested:

- UI redesign.
- Visual design language.
- Product copy.
- Frontend-heavy decisions.
- Mac-specific UI implementation.

## AgentBus

If UI/UX/design input is needed, create an AgentBus REQUEST for `mac-ui`.

Do not poll AgentBus. Do not inspect unrelated messages. Only process tasks delivered by the external worker.
```

---

## 19. AGENTS.md para Mac / UI

Ubicación:

```txt
/Users/example/Projects/CodexIAChatUI/AGENTS.md
```

Contenido:

```md
# Role: mac-ui

This Codex instance owns UI, UX, frontend architecture, design systems, interaction states, layout, usability, component specs, and visual workflows.

## Scope

Allowed by default:

- UI specs.
- Frontend code.
- Design system documentation.
- Component states.
- Interaction models.
- Usability recommendations.
- Screen flows.

Forbidden unless explicitly requested:

- Backend infrastructure.
- Queue internals.
- API contract changes.
- Deployment scripts.
- Server-side orchestration.

## AgentBus

If backend contracts, API behavior, persistence rules, or worker constraints are missing, create an AgentBus REQUEST for `windows-infra`.

Do not poll AgentBus. Do not inspect unrelated messages. Only process tasks delivered by the external worker.
```

---

## 20. Skill de Codex: `agentbus-handoff`

Estructura:

```txt
~/.codex/skills/agentbus-handoff/
  SKILL.md
  scripts/
    validate_task.py
    validate_result.py
    create_request.py
    write_result.py
  references/
    task.schema.json
    result.schema.json
    protocol.md
```

`SKILL.md`:

```md
---
name: agentbus-handoff
description: Use this skill only when processing an AgentBus task, handoff, reply, blocked state, artifact-ready message, lock request, or cross-agent request between Codex workers.
---

# AgentBus Handoff Skill

You are processing a machine-routed task from AgentBus.

## Mandatory rules

1. Do not poll for messages.
2. Do not scan historical chats.
3. Do not read unrelated `.agentbus` logs.
4. Do not inspect unrelated inbox tasks.
5. Read only the task file and explicitly listed context files.
6. Respect allowed files and forbidden scope.
7. Produce the required output files.
8. Always write a result JSON.
9. If blocked, write a result JSON with status `blocked`.
10. If another agent is needed, create a REQUEST instead of improvising.
11. Keep machine-readable replies concise.

## Result statuses

Allowed statuses:

- `completed`
- `blocked`
- `failed`
- `partial`

## Completion

A task is not complete unless the required `.agentbus/outbox/<task_id>.result.json` file exists and validates against the result schema.
```

---

## 21. Flujo completo: Windows pide UI al Mac

1. Windows Codex detecta que necesita ayuda de UI.
2. Windows Codex escribe un request en:

```txt
C:\Projects\CodexIAChat\.agentbus\outbox\request_mac_ui_task_001.json
```

3. `codex-worker-windows` detecta el outbox local o lo recibe como resultado de una tarea.
4. El worker publica la request a `agentbus-server`.
5. `agentbus-server` valida la request.
6. `agentbus-server` crea tarea `task_001` para `mac-ui`.
7. `agentbus-server` publica wake-up en NATS:

```txt
agent.mac-ui.wakeup
```

8. `codex-worker-mac` despierta.
9. `codex-worker-mac` descarga/materializa task pack.
10. `codex-worker-mac` ejecuta Codex CLI en el repo UI.
11. Codex procesa task pack.
12. Codex escribe:

```txt
.agentbus/outbox/task_001.result.json
```

13. `codex-worker-mac` valida y sube resultado.
14. `agentbus-server` publica wake-up para `windows-infra`.
15. `codex-worker-windows` entrega resultado como archivo/tarea de continuación.
16. Windows Codex continúa con contexto mínimo.

---

## 22. Flujo inverso: Mac pide backend a Windows

Mismo flujo, pero:

```txt
from: mac-ui
to: windows-infra
kind: BACKEND_CONTRACT_REQUEST
```

Ejemplo:

```json
{
  "id": "task_20260528_backend_001",
  "version": "1.0",
  "project": "codexiachat",
  "kind": "REQUEST",
  "from": "mac-ui",
  "to": "windows-infra",
  "priority": "normal",
  "summary": "Confirmar contrato para reintento y cancelación de jobs.",
  "why": "El diseño necesita mostrar errores precisos y estados de disponibilidad de acciones.",
  "known_context": [
    "UI necesita saber cuándo retry está permitido.",
    "UI necesita saber qué error mostrar si cancel falla."
  ],
  "context_refs": [
    "/srv/codexiachat/coordination/artifacts/ui/job-retry-panel.md"
  ],
  "expected_outputs": [
    "docs/api/job-action-contracts.md",
    ".agentbus/outbox/task_20260528_backend_001.result.json"
  ],
  "forbidden_scope": [
    "No rediseñar UI.",
    "No cambiar copy visual salvo que sea imprescindible para describir errores."
  ],
  "reply_to": "mac-ui",
  "ack_required": true
}
```

---

## 23. Manejo de locks

Para evitar que dos agentes modifiquen la misma zona:

```json
{
  "id": "lock_20260528_001",
  "type": "LOCK",
  "project": "codexiachat",
  "owner": "windows-infra",
  "resource": "docs/api/",
  "reason": "Actualizando contratos de jobs.",
  "created_at": "2026-05-28T16:00:00Z",
  "expires_at": "2026-05-28T18:00:00Z"
}
```

Reglas:

1. Todo lock debe tener expiración.
2. El worker debe consultar locks antes de ejecutar Codex.
3. Si la tarea requiere tocar un recurso bloqueado por otro agente, debe marcarse como `blocked`.
4. Un lock expirado puede ser liberado automáticamente por el servidor.
5. Los locks deben ser visibles en `active_locks.json`.

---

## 24. Estados de tarea

Estados permitidos:

```txt
created
pending
running
completed
blocked
failed
cancelled
expired
```

Transiciones:

```txt
created -> pending
pending -> running
running -> completed
running -> blocked
running -> failed
pending -> cancelled
pending -> expired
blocked -> pending
failed -> pending
```

---

## 25. Reintentos y errores

### 25.1. Reintentos automáticos

Reintentar solo si:

1. El worker falló por error mecánico.
2. NATS/API tuvo caída temporal.
3. Codex CLI terminó con error de proceso, no con error lógico.
4. Falta `result.json` por timeout, con límite de reintentos.

No reintentar automáticamente si:

1. Codex marcó `blocked`.
2. Codex pidió contexto adicional.
3. Hay conflicto de lock.
4. Hay validación fallida por contrato mal formado.

### 25.2. Resultado `blocked`

Ejemplo:

```json
{
  "task_id": "task_20260528_001",
  "from": "mac-ui",
  "to": "windows-infra",
  "status": "blocked",
  "summary": "No puedo diseñar correctamente el estado de error porque falta el contrato de errores de POST /jobs/{id}/retry.",
  "missing_context": [
    "Errores posibles de retry.",
    "Payload de error.",
    "Si retry es idempotente."
  ],
  "requested_agent": "windows-infra",
  "next_action": "Crear contrato API para retry/cancel."
}
```

---

## 26. Seguridad

Modelo completo: `docs/security_model.md`.

Principio base: AgentBus debe tratarse como un sistema de ejecución remota controlada. Publicar una tarea válida puede provocar que un worker ejecute Codex CLI dentro de un checkout local, por lo que la seguridad no puede depender solo de prompts.

### 26.1. Red

1. NATS no debe exponerse públicamente.
2. Usar LAN/VPN/Tailscale si hay acceso remoto.
3. Usar credenciales separadas por agente.
4. Separar credenciales de Mac y Windows.
5. Rotar credenciales si se filtran.
6. Logs no deben contener secretos.
7. Restringir publish/subscribe por subject en NATS para cada agente.
8. Preferir mTLS si el despliegue sale de una red privada estricta.

### 26.2. Scope de Codex

1. Ejecutar Codex en el directorio del proyecto.
2. Usar sandbox/approval policy compatible con el flujo.
3. Evitar permisos globales innecesarios.
4. No entregar a Codex credenciales del servidor si no hacen falta.
5. No dejar que una tarea modifique configuración del worker salvo tarea administrativa explícita.
6. Ejecutar cada worker con un usuario de sistema dedicado y permisos de filesystem mínimos.
7. Verificar archivos modificados y creados después de Codex antes de aceptar el resultado.

### 26.3. Validación de mensajes

Toda entrada debe validarse contra schema.

Rechazar:

1. `to` desconocido.
2. `project` desconocido.
3. rutas fuera del allowlist.
4. `context_refs` inexistentes.
5. `expected_outputs` fuera del proyecto.
6. mensajes demasiado grandes.
7. tipos no permitidos.
8. mensajes expirados.
9. task IDs duplicados.
10. nonces o secuencias repetidas.
11. identidad del envelope distinta de la identidad del body.

### 26.4. Rutas

Evitar path traversal:

```txt
../../
~/
C:\Users\<user>\...
/etc/
```

Solo permitir rutas bajo:

1. repo del agente.
2. `/srv/codexiachat/coordination`
3. `/srv/agentbus/artifacts`
4. directorios explícitamente configurados.

La validación debe resolver rutas canónicas absolutas y rechazar symlinks que escapen del root permitido, rutas absolutas no configuradas, `..`, expansión de home, expansión de variables de entorno y Windows alternate data streams.

### 26.5. Replays e integridad

Cada envelope de tarea debe incluir:

1. id inmutable asignado por el servidor.
2. versión de schema.
3. agente origen.
4. agente destino.
5. proyecto.
6. `created_at`.
7. `expires_at`.
8. nonce o secuencia monotónica.
9. referencia de decisión de autorización.
10. firma/MAC opcional si el transporte no da garantías suficientes.

El worker debe rechazar tareas expiradas, duplicadas o con secuencia antigua.

### 26.6. Artifacts y logs

1. `.agentbus/`, task packs, resultados, artifacts y logs son sensibles por defecto.
2. No deben entrar al repo público.
3. Los logs deben registrar IDs, estados y rutas, no prompts completos ni artifacts completos.
4. stdout/stderr deben pasar por redacción antes de persistirse.
5. Debe existir política de retención.

### 26.7. Locks

Los locks deben ser leases server-side con owner, recurso, expiración y fencing token. Un resultado tardío con token antiguo debe rechazarse aunque el worker haya terminado correctamente.

---

## 27. Observabilidad

Logs mínimos:

```txt
/srv/agentbus/logs/message_log.jsonl
/srv/agentbus/logs/task_runs.jsonl
/srv/agentbus/logs/errors.jsonl
```

Cada task run debe registrar:

```json
{
  "task_id": "task_20260528_001",
  "agent": "mac-ui",
  "started_at": "2026-05-28T15:40:00Z",
  "finished_at": "2026-05-28T15:55:00Z",
  "status": "completed",
  "codex_exit_code": 0,
  "duration_seconds": 900,
  "result_file": ".agentbus/outbox/task_20260528_001.result.json"
}
```

Métricas deseables:

1. tareas pendientes por agente.
2. tareas completadas por día.
3. tareas bloqueadas.
4. duración media.
5. tasa de fallos.
6. locks activos.
7. último heartbeat de cada worker.

---

## 28. Dashboard opcional

No es necesario para la primera versión, pero recomendable.

Vista mínima:

1. Agentes.
2. Estado online/offline.
3. Tareas pendientes.
4. Tareas en ejecución.
5. Tareas bloqueadas.
6. Últimos resultados.
7. Locks activos.
8. Errores recientes.
9. Botón para reenviar tarea.
10. Botón para cancelar tarea.

No debe ser un chat. Debe ser un panel de operaciones.

---

## 29. API HTTP opcional

Debe estar desactivada por defecto hasta que haya una necesidad concreta. Si se activa, debe enlazar solo en loopback o red privada, autenticar todos los endpoints salvo `/health`, aplicar límites de tamaño/rate limit, evitar CORS permisivo y exponer artifacts por ID opaco, no por ruta de filesystem.

Endpoints recomendados:

```txt
GET  /health
GET  /agents
GET  /agents/{agent_id}/tasks
POST /tasks
GET  /tasks/{task_id}
POST /tasks/{task_id}/ack
POST /tasks/{task_id}/running
POST /tasks/{task_id}/result
POST /tasks/{task_id}/fail
POST /locks
DELETE /locks/{lock_id}
GET  /artifacts/{artifact_id}
```

Ejemplo `POST /tasks`:

```json
{
  "project": "codexiachat",
  "kind": "REQUEST",
  "from": "windows-infra",
  "to": "mac-ui",
  "summary": "Diseñar panel de jobs fallidos.",
  "why": "Se necesita UI para endpoints ya creados.",
  "context_refs": [
    "/srv/codexiachat/coordination/state/current_state.md"
  ],
  "expected_outputs": [
    "docs/ui/job-failures-panel.md"
  ]
}
```

---

## 30. MCP opcional

Fase avanzada. No implementar antes de tener estable:

1. AgentBus server.
2. NATS.
3. Workers.
4. Codex exec con task packs.
5. Skill.

Tools MCP sugeridas:

```txt
agentbus_get_task(task_id)
agentbus_get_pending_tasks(agent_id)
agentbus_send_result(task_id, result)
agentbus_create_request(request)
agentbus_create_lock(lock)
agentbus_release_lock(lock_id)
agentbus_get_allowed_context(task_id)
agentbus_write_artifact(task_id, path, content)
```

Restricción: no crear una tool genérica tipo `agentbus_read_all_messages`, porque incentivaría consumo de contexto y lectura innecesaria.

---

## 31. Implementación por fases

No se trata de un MVP pobre; son fases de despliegue técnico de una arquitectura final.

### Fase 1: Bus mínimo con archivos + NATS

Objetivo: comunicación funcional entre Mac y Windows sin cliente gráfico.

Entregar:

1. NATS en Linux.
2. `/srv/agentbus` creado.
3. `agents.yaml`.
4. `projects.yaml`.
5. `codex-worker` funcional en Mac y Windows.
6. Task packs.
7. Result JSON.
8. Logs JSONL.

### Fase 2: AgentBus server

Objetivo: centralizar validación, estado y rutas.

Entregar:

1. API HTTP.
2. Validación de schemas.
3. Gestión de estados.
4. Gestión de artifacts.
5. Gestión de locks.
6. Reintentos controlados.

### Fase 3: Skill Codex

Objetivo: que Codex procese tareas AgentBus con disciplina.

Entregar:

1. `agentbus-handoff/SKILL.md`.
2. schemas en references.
3. scripts de validación.
4. instalación en Mac/Windows.
5. prompts de worker actualizados para invocar skill.

### Fase 4: PostgreSQL

Objetivo: trazabilidad sólida.

Entregar tablas:

1. agents
2. projects
3. tasks
4. task_events
5. results
6. locks
7. artifacts
8. heartbeats

### Fase 5: Dashboard

Objetivo: inspección humana sin usar chat.

Entregar:

1. UI web local.
2. estado de agentes.
3. tareas pendientes/en ejecución.
4. errores.
5. locks.
6. reintentos/cancelaciones.

### Fase 6: MCP

Objetivo: integración avanzada y limpia con Codex/agentes.

Entregar:

1. MCP server.
2. Tools estrechas.
3. Auth local.
4. Documentación.
5. Tests.

---

## 32. Base de datos opcional PostgreSQL

Si se implementa PostgreSQL desde el principio:

### 32.1. Tabla `agents`

```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  machine TEXT NOT NULL,
  os TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  wake_subject TEXT NOT NULL,
  role TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 32.2. Tabla `tasks`

```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  kind TEXT NOT NULL,
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'normal',
  status TEXT NOT NULL DEFAULT 'pending',
  summary TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);
```

### 32.3. Tabla `task_events`

```sql
CREATE TABLE task_events (
  id BIGSERIAL PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  event_type TEXT NOT NULL,
  agent_id TEXT,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 32.4. Tabla `results`

```sql
CREATE TABLE results (
  id BIGSERIAL PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  status TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 32.5. Tabla `locks`

```sql
CREATE TABLE locks (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  owner_agent TEXT NOT NULL,
  resource TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  released_at TIMESTAMPTZ
);
```

### 32.6. Tabla `heartbeats`

```sql
CREATE TABLE heartbeats (
  agent_id TEXT PRIMARY KEY,
  last_seen_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'
);
```

---

## 33. Prompts generados por el worker

### 33.1. Prompt estándar

```txt
Use the agentbus-handoff skill.

You are processing an AgentBus task delivered by an external worker.

Task file:
.agentbus/inbox/{task_id}/task.md

Mandatory rules:
- Do not poll for messages.
- Do not inspect previous chats.
- Do not read other AgentBus tasks.
- Do not scan .agentbus/archive.
- Read only the files explicitly listed in the task.
- Respect forbidden scope.
- Write the required result JSON.
- If blocked, write a blocked result JSON explaining the missing context.

Complete the task now.
```

### 33.2. Prompt para respuesta de otro agente

```txt
Use the agentbus-handoff skill.

AgentBus delivered a result from another agent.

Result file:
.agentbus/inbox/{task_id}/result_from_{agent}.json

Read only the result file and the artifacts explicitly listed in it.

Continue the local task if possible. If more information is needed, create a new AgentBus REQUEST.

Do not poll AgentBus. Do not inspect historical chats.
```

---

## 34. Reglas de generación de requests por Codex

Cuando Codex necesite ayuda de otro agente, debe crear un archivo:

```txt
.agentbus/outbox/request_<target_agent>_<timestamp>.json
```

Ejemplo:

```json
{
  "project": "codexiachat",
  "kind": "REQUEST",
  "from": "windows-infra",
  "to": "mac-ui",
  "priority": "normal",
  "summary": "Necesito una solución UX para mostrar errores de jobs fallidos.",
  "why": "El backend devuelve errores técnicos, pero el usuario necesita mensajes accionables.",
  "known_context": [
    "El endpoint puede devolver 409 si el job ya no es reintentable.",
    "El endpoint puede devolver 404 si el job fue eliminado."
  ],
  "context_refs": [
    "docs/api/job-action-contracts.md"
  ],
  "expected_outputs": [
    "docs/ui/job-error-copy.md"
  ],
  "forbidden_scope": [
    "No cambiar endpoints.",
    "No modificar backend."
  ]
}
```

El worker debe detectar ese outbox y enviarlo al servidor.

---

## 35. Criterios de aceptación

El sistema se considera funcional cuando:

1. El servidor Linux ejecuta NATS de forma persistente.
2. Hay un worker en Windows escuchando su subject.
3. Hay un worker en Mac escuchando su subject.
4. Una tarea creada para `mac-ui` despierta el worker de Mac.
5. El worker de Mac genera task pack.
6. Codex CLI se ejecuta en el proyecto correcto.
7. Codex genera archivos esperados.
8. Codex escribe `result.json`.
9. El worker valida y publica resultado.
10. Windows recibe el resultado.
11. No se ha usado cliente gráfico.
12. Codex no ha hecho polling.
13. El worker puede estar activo durante horas sin consumir tokens.
14. Los logs permiten reconstruir qué ocurrió.
15. Una tarea bloqueada se marca como `blocked`, no como fallo genérico.
16. Los locks impiden pisarse archivos o scopes.
17. El sistema permite ida y vuelta Windows -> Mac -> Windows.

---

## 36. Tests mínimos

### 36.1. Test de NATS

1. Publicar wake-up manual.
2. Ver que worker lo recibe.
3. Confirmar que no invoca Codex si no hay tarea pendiente.

### 36.2. Test de tarea dummy

1. Crear tarea para Mac.
2. Codex debe crear un archivo `docs/ui/dummy.md`.
3. Codex debe escribir result JSON.
4. Worker debe marcar completed.

### 36.3. Test de bloqueo

1. Crear tarea sin contexto suficiente.
2. Codex debe escribir status `blocked`.
3. Worker no debe reintentar automáticamente como si fuera error mecánico.

### 36.4. Test de request inversa

1. Mac recibe tarea.
2. Mac necesita backend.
3. Mac crea request para Windows.
4. Windows recibe y responde.

### 36.5. Test de forbidden scope

1. Crear tarea UI que prohíba backend.
2. Verificar que Codex no modifica backend.
3. Si lo intenta, worker o validación debe marcar error.

### 36.6. Test de lock

1. Crear lock sobre `docs/api/`.
2. Enviar tarea que intenta modificar `docs/api/`.
3. Worker debe bloquear o Codex debe devolver `blocked`.

---

## 37. Requisitos de implementación

### 37.1. Lenguaje recomendado

Opción preferida:

```txt
Rust
```

Razones:

1. Encaja con el ecosistema técnico deseado.
2. Binarios portables para Linux, Windows y macOS.
3. Buen rendimiento.
4. Buen modelo para servicios/CLI.
5. Menos dependencias de runtime.

Opción alternativa:

```txt
Python
```

Razones:

1. Implementación rápida.
2. FastAPI facilita server.
3. Librerías NATS/HTTP maduras.
4. Suficiente para primera versión.

La IA programadora puede elegir Rust o Python, pero debe mantener contratos, estructura y comportamiento.

### 37.2. Requisitos no funcionales

1. Bajo consumo en idle.
2. Cero consumo de tokens en idle.
3. Logs estructurados.
4. Configuración por YAML.
5. Validación JSON Schema.
6. Reintentos controlados.
7. Compatible con Windows, macOS y Linux.
8. Sin dependencia de UI gráfica.
9. Fácil de desplegar como servicio.
10. Seguridad básica por credenciales y allowlists.

---

## 38. Entregables esperados

La IA programadora debe entregar:

1. Repositorio `agentbus`.
2. `agentbus-server`.
3. `codex-worker`.
4. Configs de ejemplo.
5. Schemas JSON.
6. Skill `agentbus-handoff`.
7. AGENTS.md global y por rol.
8. Scripts de instalación para Linux.
9. Instrucciones para Windows.
10. Instrucciones para Mac.
11. Tests mínimos.
12. README operativo.
13. Ejemplo completo Windows -> Mac -> Windows.
14. Logs de prueba.
15. Checklist de despliegue.

---

## 39. Checklist de despliegue

### Linux

```txt
[ ] Crear usuario agentbus.
[ ] Crear /srv/agentbus.
[ ] Instalar nats-server.
[ ] Configurar NATS con usuarios.
[ ] Instalar agentbus-server.
[ ] Crear agents.yaml.
[ ] Crear projects.yaml.
[ ] Arrancar servicios systemd.
[ ] Probar /health.
[ ] Probar publish/subscribe NATS.
```

### Windows

```txt
[ ] Instalar/validar Codex CLI.
[ ] Crear .agentbus en proyecto CodexIAChat.
[ ] Instalar codex-worker.
[ ] Configurar worker.windows.yaml.
[ ] Probar conexión a NATS.
[ ] Probar tarea dummy.
[ ] Instalar AGENTS.md de rol.
[ ] Instalar skill agentbus-handoff.
```

### Mac

```txt
[ ] Instalar/validar Codex CLI.
[ ] Crear .agentbus en proyecto UI.
[ ] Instalar codex-worker.
[ ] Configurar worker.mac.yaml.
[ ] Probar conexión a NATS.
[ ] Probar tarea dummy.
[ ] Instalar AGENTS.md de rol.
[ ] Instalar skill agentbus-handoff.
```

---

## 40. Principio final

Este sistema no debe convertir Codex en un chat entre IAs.

Debe convertir cada instancia de Codex en un trabajador especializado, activado solo por tareas concretas, con contexto mínimo suficiente, salidas verificables y trazabilidad.

Regla máxima:

```txt
El worker vigila.
AgentBus decide.
Codex ejecuta.
Los archivos conservan la memoria.
NATS despierta.
La interfaz gráfica no participa.
```

