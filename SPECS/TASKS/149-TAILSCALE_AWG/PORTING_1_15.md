# Перенос AWG/Tailscale на upstream/testing (1.15)

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).
**Статус:** аудит исходников; перенос/сборка/data-plane приёмка1.15 не выполнены.

## Закреплённый срез

Проверен SagerNet/sing-box testing
[`e5d91fa79f6319d5de940d6c81d81f0fe53b9476`](https://github.com/SagerNet/sing-box/tree/e5d91fa79f6319d5de940d6c81d81f0fe53b9476).
Ключевой commit
[`5a1012dfeea6f7d6e8c1f1cfee2ca6bb414c7a59`](https://github.com/SagerNet/sing-box/commit/5a1012dfeea6f7d6e8c1f1cfee2ca6bb414c7a59)
меняет активные Tailscale/WireGuard stack implementations и build tags.

Pins из go.mod этого среза:

| Dependency | Revision |
|---|---|
| SagerNet tailscale | 670967df7dbf74036e4fd354f1b803ff194b4723 |
| SagerNet sing-tun | 5b0a1a7a394ed49d1a1adab3877284b86a8af94e |
| SagerNet wireguard-go | fdf0ad04658666a57f15da1b0eea30c08b0a94db |

Module archives получены с проверкой Go module sums. Pins действующей1.14,
четыре downstream gitlinks и dependency patch bytes не менялись. Testing не
сливался в рабочую ветку; новых release artifacts не собиралось.

## Фактические изменения gVisor/stack

- `protocol/tailscale/*.go` теперь gated `with_tailscale`, вместо старой
  комбинации с `with_gvisor`. Include stub больше не требует gVisor.
- Tailscale Endpoint использует `*tun.Go`, `server.NetstackHandler` и
  `server.ExportNetstack().ExportIPStack()`. Старые gVisor tcpip/gonet handlers
  заменены интерфейсами нового стека, включая `tun.Port`, return paths, NAT
  mapping/filtering и memory-pressure callbacks.
- `transport/wireguard` НЕ удалён. Device и stackDevice переписаны на
  `tun.NewGo`, MemoryTun/peerRouter; удалены stack-gonet helpers и old stubs.
  Меняется `Device.SetDevice`: принимает WireGuard device И peers; маршрутизация
  использует AllowedIPs/peer callbacks и UDP/fragment handling.
- В pinned Tailscale dependency `wgengine/netstack` также использует sing-tun.
  Место ранней device initialization/cleanup в userspace engine ещё есть.
- «gVisor полностью отсутствует» было бы неточно: testing go.mod сохраняет
  indirect gVisor dependency, а pinned sing-tun содержит optional legacy
  gvisor/mixed/system stack implementations. Default empty/go stack и активные
  WireGuard/Tailscale endpoints уже используют новый Go stack. Отсутствие
  with_gvisor в endpoint не означает нулевой gVisor module graph.

Исходники для проверки: [Tailscale endpoint](https://github.com/SagerNet/sing-box/blob/e5d91fa79f6319d5de940d6c81d81f0fe53b9476/protocol/tailscale/endpoint.go),
[WireGuard device](https://github.com/SagerNet/sing-box/blob/e5d91fa79f6319d5de940d6c81d81f0fe53b9476/transport/wireguard/device.go),
[WireGuard stack](https://github.com/SagerNet/sing-box/blob/e5d91fa79f6319d5de940d6c81d81f0fe53b9476/transport/wireguard/device_stack.go),
[Tailscale netstack](https://github.com/SagerNet/tailscale/blob/670967df7dbf74036e4fd354f1b803ff194b4723/wgengine/netstack/netstack.go),
[sing-tun stack selector](https://github.com/SagerNet/sing-tun/blob/5b0a1a7a394ed49d1a1adab3877284b86a8af94e/stack.go).

## Что переносить, что переиспользовать

Нельзя просто перенести1.14 endpoint целиком или удалить слово with_gvisor
из guard. Сначала сохранить новую upstream структуру endpoint/stack и внести
только AWG seams: options, pre-Up hook, status и scoped carrier. Затем обновить
согласованный набор include/protocol/daemon/libbox capability tags: в1.14 они
правильно требуют gVisor, в1.15 должны следовать реальным новым parent tags.

AWG framing/IPC/decoy codec привязан к WireGuard device API, не к gVisor. Поэтому
сохраняем helpers/tests/fixtures в transport/wireguard и узкий typed compiler;
новый общий пакет не нужен. Это уменьшает diff, но не доказывает совместимость
новых stack/NAT/return paths или fork-submodule APIs. Новые upstream gitlinks/
module pins нельзя принимать поверх downstream AWG fixes без отдельного merge.

Три действующих patches (`awg-device`, `derp-borrowed-read-ack`, `security-serve`)
проверены `git apply --check` на новом pinned Tailscale source: все3 проходят,
для нескольких hunks нужны offsets. Это только применимость текстовых hunks;
патчи не устанавливались в module cache. Компиляция, порядок cleanup/Up, race,
security semantics и реальный transport при1.15 не проверены. Нельзя объявлять
весь порт простым или несовместимым только по этому результату.

## План отдельного порта

1. Зафиксировать baseline/Go/dep pins1.15; отдельно обновить downstream
   sing-tun/wireguard-go forks, сохранив AWG и platform fixes.
2. Переустановить minimal AWG hooks поверх нового TS base, перепроверить
   classifier, direct/DERP carrier, borrowed-ACK и Serve security gates.
3. Внести AWG option/status seams в новые endpoints, обновить parent-tag
   requirements; не возвращать старый gVisor stack и не заявлять capability
   раньше успешной сборки. Перегенерировать protobuf/FFI, если upstream API
   требует этого, и синхронизировать consumers.
4. Принять новые stack/peerRouter/AllowedIPs, TCP/UDP/fragment и return-path
   semantics, memory pressure, shutdown/rekey/reload и смену сети. Проверить
   DNS и отсутствие private leaks с VLESS/carrier/mixin guards.
5. Повторить isolated plain WG/AWG2/AWG3 direct/DERP TCP/UDP/checksum/cookie/
   rekey matrix, затем Linux/Android native route/DNS tests. Windows/macOS и
   остальные platform/release gates принимаются отдельно.

Отдельный1.15 port остаётся открытым; этот аудит не меняет работающую1.14.
