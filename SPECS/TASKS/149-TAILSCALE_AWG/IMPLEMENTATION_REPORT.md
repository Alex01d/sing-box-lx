# IMPLEMENTATION REPORT —149

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).
**Состояние:** engineering contribution для командной проверки; release и
полная пяти платформенная приёмка не завершены.

## Реализация

- Optional typed endpoints[].awg (version2/3), WireGuard-owned validation/codec и
  build capability with_tailscale_awg. Invalid/unsupported profiles fail closed.
- Per-device ранний hook, framing classifier direct/DERP, headroom8, scoped
  profile/carrier lifecycle; thin pinned dependency patches и security guards.
- auto/derp carrier поверх выбранного outbound, control/DERP также внутри
  carrier, без native fallback при outer outage.
- Optional safe transport status через existing adapter/protobuf/libbox.
  Existing RPC и WG session counters сохраняются.
- Reusable isolated Headscale/reference/private-services/VLESS test tools;
  TLS с test-only CA, immutable source pins/patch hashes.
- Default release dependency не заменена локальным fork; opt-in engineering
  bootstrap создаёт внешний workspace. Published patched dependency pin открыт.

## Source sync и публичная подготовка

Текущая ветка синхронизирована с origin/lx
`def84828b069eb6c7cb15c0017ee33b2abdb907e`. Incoming published task148 относится
к OOM runtime memory; unpublished AWG task перенумерована149. Общий индекс
сохраняет обе задачи. Generated protobuf регенерируется после source merge с
transport17, session6/7 и memoryRuntime10. Default build и профильные проверки
записываются ниже после текущего прогона.

Локальные changes и исходные документы сохранены во внешнем private backup до
редактирования. Публичная дельта содержит только reusable implementation/specs/
fixtures/tooling. Устройства, infrastructure topology, deployment receipts,
реальные endpoints/profiles/identities, paths и binaries исключены.

## Граница доказательств

Ранее engineering implementation проверялась isolated direct/forced DERP
TCP16MiB/UDP с independent reference, VLESS parallel/carrier, negative routing/
DNS gates и bounded requests. Вклад не заявляет повтор этой полной матрицы на
каждом source sync. Текущие source/build checks перечисляются отдельно.

Длительные Android DERP timeouts остаются открытым stability gate: borrowed-ACK
regression доказывает узкий lifecycle defect, не причинность каждого timeout.
Mobile handoff, Windows/macOS fixes/native acceptance, iOS Packet Tunnel,
consumer CI и публикация release dependency pin остаются открыты.

## Текущие проверки после синхронизации

- Default canonical CLI build с GOWORK=off — PASS.
- Opt-in canonical AWG build через pinned/checksummed external bootstrap — PASS.
- TestTailscaleAWGProfileValidationLX, TestTailscaleDNSIsolationRegressionLX и
  TestAwgKeepaliveSpec — PASS, только эти named regressions.
- CLI config boundaries:14cases PASS, включая missing-capability fail-closed
  и обычный Tailscale без integration tag.
- Reference overlay helpers:9tests PASS на чистом pinned reference; Python
  tooling syntax — PASS. Исходный harness attempt с отсутствующим checkout
  сохранён отдельно и не считается product failure.
- Проверка known personal/infrastructure identifiers в curated source — PASS.
  Binary TLS fixtures перенесены byte-identical из уже публичного baseline.
- Generated stubs:58RPCs, transport17, session6/7, memoryRuntime10; formatter
  ограничен generated files, посторонние изменения генератора восстановлены.

Полная isolated traffic matrix повторно не запускалась: incoming source sync
меняет OOM/status, а transport patch/codec pins не изменены. Windows/macOS и
остальные release/platform gates остаются открыты.

## Ревью границы transport/wireguard

Убран отдельный transport/awgprofile и делегирующие wrappers. Codec/helpers/
tests/testdata возвращены на исходные пути;20 legacy files совпадают с
origin/lx byte-for-byte. Восстановлен исходный AWG3 peer-config regression,
отдельный дублирующий test удалён. protocol/tailscale импортирует WireGuard
напрямую через CompileTailscaleAWGProfile/TailscaleAWGProfile.Apply; raw IPC
остаётся private. Profile/frame/fingerprint semantics не менялись.

Проверки после изменения:

- Import graph подтверждает protocol/tailscale → transport/wireguard и отсутствие
  обратного импорта/нового пакета; полный AWG CLI собирается.
- Named no-AWG stub, AWG2/3/profile/MASQUE/QUIC/capture regressions, gVisor profile
  и обычный Tailscale DNS regression — PASS. AWG helpers компилируются и
  проверяются без with_gvisor; текущий1.14 endpoint guard сохранён.
- Канонические обычный и opt-in AWG CLI builds — PASS. Tagless go build ./...
  с требуемым -ldflags=-checklinkname=0 — PASS. Без этого flag bare build
  останавливается на runtime/pprof linkname в существующем experimental/boxdd;
  эта область не менялась.
-14 CLI config/capability boundaries и дополнительный synthetic AWG3.1 profile
  check — PASS. Dependency patch bytes, proto/schema и submodule pins прежние.
- CI вновь использует исходный transport/wireguard package для всех legacy
  codec regressions; отдельный package list не нужен, named DNS gate сохранён.

[PORTING_1_15.md](PORTING_1_15.md) описывает проверенный testing с новым
sing-tun.Go: это source audit/patch applicability, не готовый порт и не runtime
приёмка1.15. Новые client/router binaries не развёртывались.
