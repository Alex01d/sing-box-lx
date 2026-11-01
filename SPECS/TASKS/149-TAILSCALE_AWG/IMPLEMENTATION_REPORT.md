# IMPLEMENTATION REPORT —149

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).
**Состояние:** engineering contribution для командной проверки; release и
полная пяти платформенная приёмка не завершены.

## Реализация

- Optional typed endpoints[].awg (version2/3), shared validation/codec и
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
  TestAwgKeepalivePeerConfigLX — PASS, только эти named regressions.
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

CI package lists дополнены transport/awgprofile после переноса существующих
codec tests; ordinary Tailscale DNS regression зарегистрирован по имени и
также прошёл локально без integration tag/external workspace. Workflow YAML
разбирается, curated Go files проходят gofmt, git diff --check — PASS.
