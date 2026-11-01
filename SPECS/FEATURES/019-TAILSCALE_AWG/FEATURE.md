# FEATURE019 — Embedded Tailscale с AmneziaWG

**Статус:** engineering implementation; полная platform/release acceptance открыта.
**Задача:** [149-TAILSCALE_AWG](../../TASKS/149-TAILSCALE_AWG/SPEC.md).

## Пользовательский результат

Один embedded Tailscale endpoint подключается к обычному Headscale и использует
WireGuard, AWG2 либо AWG3.x data plane. Private назначения доступны через
совместимый peer/subnet-router, выбранный internet трафик — через существующий
VLESS outbound. Профиль меняет framing; identity, ACL и route approval остаются
штатными. Fork Headscale не требуется, а обычный standalone AWG peer не заменяет
совместимый Tailscale router.

Endpoint может использовать native underlay либо внешний detour. `auto`
сохраняет peer UDP при поддержке multi-destination carrier; `derp` использует
TCP-only DERP carrier. Explicit detour охватывает control/DERP и имеет приоритет
над ambient proxy; outer outage не разрешает незаметный native fallback.

## Контракт

- Optional typed `endpoints[].awg`: version2/3, profile ID, shared parameters.
  AWG3 family включает3.1 header protection/padding/random trailers/timers.
- Новый build/capability tag with_tailscale_awg. Неполная capability явно
  отвергает профиль до запуска, обычный Tailscale без awg сохраняется.
- Optional safe status: configured/applied mode, profile ID/fingerprint,
  applied flag/error отдельно от peer availability. Secrets в status не входят.
- Профиль изолирован между endpoints, сохраняется при rekey/reload. Identity
  существующего устройства не меняется при edit/restart; export её не переносит.
- Shared validation/codec сохраняет совместимость standalone WG/AWG.

## Пять платформ

Linux/Windows/macOS используют launcher, Android — LxBox, iOS — настоящий
Packet Tunnel с native bridge. Общий schema/UI-контракт: optional auth key и
interactive login, WireGuard/AWG2/AWG3, import/edit/save/export, status.
Потребитель сохраняет private CIDR/DNS guards независимо от login/live routes и
отвергает unsupported transport атомарно. Protected data/DNS при отказе не
выходит через direct или public proxy.

Порядок приёмки: Linux engineering, Android engineering, затем Windows/macOS,
последним iOS. Публичная ветка предназначена для совместной проверки; наличие
Flutter scaffold, source-level tests или control handshake не является готовой
платформенной VPN интеграцией. Mobile handoff, длительная DERP stability,
Windows/macOS route/DNS/handoff и iOS/signing gates принимаются отдельно.

## Границы реализации

Тонкий descendant закреплённой SagerNet Tailscale dependency, без копирования
стороннего fork целиком. Engineering bootstrap из public immutable base и
checksum-verified patches создаёт внешний go.work; default/release dependency
пока прежняя. Новый опубликованный immutable dependency pin — отдельный gate.
AWG peer relay и встроенный SSH server временно запрещены до отдельного
compatibility/security gate. Headscale/DERP HTTPS protocol obfuscation, remote
profile provisioning и массовая миграция пользователей в scope не входят.

Изолированные tests и инструкции — [lab](../../../lx-test/tailscale-awg/README.md),
граница dependency/security — [COMPATIBILITY](../../TASKS/149-TAILSCALE_AWG/COMPATIBILITY.md).
