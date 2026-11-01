# SPEC: 149 — Embedded Tailscale с AmneziaWG

**Фича:** [019-TAILSCALE_AWG](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).
**Статус:** engineering implementation; release/platform acceptance открыта.

## Назначение и границы

Добавить AWG2 и AWG3.x data-plane framing к embedded Tailscale endpoint,
сохранив штатный Headscale control plane, identity, ACL, route approval, NAT
traversal и DERP. Совместимый Tailscale peer/router получает тот же профиль.
Обычный standalone AWG peer не становится Tailscale node. AWG не скрывает сам
Headscale/DERP HTTPS; изменение их протокола в scope не входит.

Реализация тонкая: существующая SagerNet Tailscale линия плюс per-device seams;
сторонний Tailscale fork целиком, CLI/preferences и DISCO profile sync не
переносятся. WireGuard crypto/identity/key lifecycle остаются в pinned codec.

## Конфигурация

```json
{
  "type": "tailscale",
  "tag": "private-net",
  "control_url": "https://headscale.example.invalid",
  "state_directory": "tailscale/private-net",
  "accept_routes": true,
  "awg": {
    "version": 2,
    "profile_id": "synthetic-example",
    "parameters": {
      "jc": 4, "jmin": 40, "jmax": 70,
      "s1": 64, "s2": 64, "s3": 32, "s4": 16,
      "h1": "100000-199999", "h2": "200000-299999",
      "h3": "300000-399999", "h4": "400000-499999"
    }
  }
}
```

Значения примера синтетические. `awg` необязателен; отсутствие/null сохраняет
обычный WireGuard framing. Заданный объект требует `version`2/3 и непустой
`parameters`. `profile_id` — необязательная метка `[A-Za-z0-9._-]{1,64}`.
Profile ID не является ключом или разрешением. Обе стороны согласуют framing.

Typed parameters переиспользуют AmneziaWGOptions и существующий codec в
transport/wireguard. protocol/tailscale импортирует этот пакет напрямую через
CompileTailscaleAWGProfile; private IPC/decoy helpers остаются внутри wireguard.
Отдельный transport/awgprofile не требуется. Profile Apply зависит от WireGuard
device API; gVisor/stack реализация не входит в эту typed границу. Текущие
Tailscale build/dependency требования проверяются отдельно от этой границы.

Параметры:

- Jc/Jmin/Jmax, S1–S4, H1–H4; диапазоны и bounds проверяются до запуска.
- AWG3 поддерживает header protection, padding, random trailers и диапазоны
  timers. Version3 — семейство wire format; параметры3.1 не требуют enum3.1.
- Header protection key декодируется в32байта; S1–S4 удовлетворяют minimum12.
  Cookie DoS protection по умолчанию остаётся включённой.
- CPS/masquerade и i1 конфликтуют по правилам standalone AWG. CR/LF/NUL,
  неизвестные поля, отрицательные/переполненные размеры и обратные диапазоны
  отклоняются; полностью необфусцирующий профиль также отклоняется.
- WG private/public keys, peers, AllowedIPs, routes, arbitrary IPC commands не
  входят в parameters. Ошибки не раскрывают key/CPS contents.

Сборка без `with_tailscale_awg` явно отвергает AWG-профиль, сохраняя обычный
Tailscale. Если задан with_tailscale_awg без supporting tags
with_gvisor/with_tailscale/with_awg, compile-time guard отвергает саму сборку:
нельзя опубликовать бинарь с ложной capability.
Consumers требуют capability и возвращают `tailscale_awg_core_unsupported` до
любого drop_node/drop_field; молчаливый fallback недопустим.

## Dependency и ранняя инициализация

Per-server initializer передаётся через engine config. Cleanup регистрируется
до вызова hook; hook применяет только проверенный typed profile до device.Up
и первого пакета. Ошибка закрывает ресурсы и прерывает startup. Nil hook
сохраняет upstream sequence. Process-global AWG overrides отсутствуют.

Фактические общие transport seams: tsnet/tsnet.go, wgengine/userspace.go,
wgengine/magicsock/magicsock.go, wgengine/magicsock/derp.go,
derp/derphttp/derphttp_client.go, control/controlhttp/client.go. Serve security
backport в ipn/ipnlocal/serve.go учитывается отдельно. Новые helpers/tests
изолированы; точные pins, budget и hashes — COMPATIBILITY.md/dependencies.json.

Framing classifier проверяет полные STUN/DISCO signatures перед широкими AWG
H ranges, затем device framing, затем Geneve. Classifier не аутентифицирует
пакеты: это обязанность WG codec. AWG peer relay и встроенный SSH server в
engineering явно запрещены до отдельных compatibility/security gates.

Default/release go.mod сохраняет published base dependency. Engineering
bootstrap воспроизводимо создаёт внешний go.work из public pinned base плюс
checksum-verified patches. Release build требует immutable опубликованный pin;
локальный путь не может быть release dependency. Module cache не патчится.

## Lifecycle и совместимость

Профиль привязан к конкретному endpoint/device и сохраняется при rekey/netmap
updates/reload. Два endpoints не разделяют профиль, bind или carrier state.
Shutdown закрывает только принадлежащие endpoint resources. Identity directory
сохраняется при редактировании/restart; export не переносит machine identity.

Сохранить send headroom8, актуальный interface monitor и scoped cleanup,
OutboundWithMultiplex и resolver/group behavior. MTU учитывает worst-case
framing/padding/UDP overhead; нельзя повышать underlay MTU или обнулять reserve
вместо исправления. Large TLS, IPv4/IPv6 payload, cookie и rekey обязательны.

DNS остаётся текущим tailnetDomains resolver: canonical names, short names,
hosts-only suffix, longest forwarded suffix, case/trailing dot и NXDOMAIN
проверяются отдельно. AWG-профиль не задаёт DNS или маршруты.

## Внешний carrier и параллельный VLESS

Разные route rules могут направлять protected назначения через Tailscale-AWG,
а internet назначения — через существующий VLESS. Для самого Tailscale endpoint
необязательный detour задаёт внешний outbound, а `underlay_mode` выбирает:

- отсутствие поля сохраняет legacy поведение при обычном Tailscale;
- `auto` передаёт peer UDP через carrier с multi-destination semantics,
  control/DERP TCP — через тот же carrier;
- `derp` выключает peer UDP и передаёт peer data через DERP TCP carrier.

Outer outbound не должен зависеть от этого endpoint; cycle отклоняется.
Explicit carrier имеет приоритет над ambient HTTP proxy. При outer outage нет
native/direct fallback. Status direct означает отсутствие DERP, а не отсутствие
внешнего proxy. Control/DERP/DNS bootstrap и socket protection не должны
рекурсивно попадать в собственный туннель.

## Status и диагностика

Optional TailscaleTransportStatus передаётся через существующий
adapter→protobuf→libbox путь; member transport занимает field17. Сохраняются
все существующие RPC/wire numbers, WG session6/7 и memoryRuntime10.
Status содержит configured/applied mode, applied flag, profile ID и
fingerprint canonical IPC, safe error; key/CPS не экспортируются.

Handshake/control login/DISCO не доказывают data plane. Используется
существующий StartConnectionTest и реальные TCP/UDP requests. HTTP403/401 с
проверенным TLS означает ответ приложения, а не transport failure.

## Потребители и приёмка

Единый profile schema применяется на пяти платформах. UI: optional auth key,
interactive Headscale login, WireGuard/AWG2/AWG3, import/edit/save/export,
configured/applied status отдельно от peer availability. Static protected CIDR
и private suffix guards сохраняются до login, после logout и при route loss.
Protected traffic/DNS не уходит в direct/VLESS при ошибке профиля/ACL/outage.
Backup новой возможности требует atomic contract/capability gating.

Последовательность engineering acceptance: Linux → Android → macOS/Windows →
iOS. iOS требует отдельный настоящий Packet Tunnel/native bridge/signing gate.
Публичный вклад не объявляет завершённую device/platform acceptance.

Функциональные и negative gates определены TEST_MATRIX.md. Изолированный стенд
не меняет host TUN/firewall/sysctl, системный tailscaled или OS CA store. Пины,
patches, synthetic fixtures и команды воспроизводимы; личные журналы и сведения
об окружении не входят в репозиторий.
