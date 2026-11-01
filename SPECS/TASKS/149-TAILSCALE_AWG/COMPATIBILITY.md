# COMPATIBILITY:149 — Embedded Tailscale AWG

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).

## Закреплённые зависимости

Public source pins и SHA256 patches —
[lx-test/tailscale-awg/dependencies.json](../../../lx-test/tailscale-awg/dependencies.json).
SagerNet Tailscale base `79c1732442a9dfba9f80512247432a6ab7faca67`,
independent LiuTangLei reference `f58b730c8c1eb30c00127e6a2ebe4fa0540d29f1`.
Candidate Go1.26.10; reference Go1.27.3. Existing four submodule gitlinks не
меняются. Synthetic fixtures не содержат реальных profiles/identities.

Default/release go.mod остаётся на published base. Engineering bootstrap
проверяет SHA256 patches и создаёт отдельный dependency checkout/go.work;
release-ready immutable patched pin пока не опубликован. Reproducible external
workspace не следует выдавать за уже обновлённую release dependency.

## Бюджет dependency

| Общий файл | Назначение |
|---|---|
| tsnet/tsnet.go | Per-server device initializer и scoped carrier/force-DERP options |
| wgengine/userspace.go | Cleanup до hook, profile до Up, carrier forwarding |
| wgengine/magicsock/magicsock.go | Framing classifier, scoped packet carrier, AWG peer-relay restriction |
| wgengine/magicsock/derp.go | Device classifier и borrowed-result ACK на закрытом bind |
| derp/derphttp/derphttp_client.go | Explicit carrier для DERP/netcheck вместо ambient proxy |
| control/controlhttp/client.go | Explicit carrier для TS2021 control dial |
| ipn/ipnlocal/serve.go | Отдельный Serve security backport |

Новые helpers/tests изолированы. Весь сторонний fork, его CLI, preference
persistence, QUIC carrier и DISCO profile sync не переносятся. AWG peer relay и
embedded SSH пока отклоняются. Classifier не заменяет WG authentication.

## Security и lifecycle backports

Serve fixes TS-2026-016/017: capability в request context и dial-time Unix-socket
guards, Linux inode pinning. Public upstream commits:
`d090b5ab68ed68fcbfc01640e72aaee34a6ceb7f`,
`21b7a44c4485ff625fa38f988daaa8a316498733`,
`7faa0a9d6f8a57fa662a4b6a53724ed18ee9306f`.
Проверяются допустимый socket и отказы self/symlink/swapped backend, включая race.
Go toolchain/security baseline проверяется отдельно от transport compatibility;
lab TLS verification включена и CA не устанавливается в OS trust store.

DERP borrowed-read hotfix: закрытый connBind.receiveDERP подтверждает
заимствованный result через copyBuf(nil) ровно один раз перед выходом. Wire
format, codec/key state, открытый receive, timers и queues не меняются. Focused
Close/Open regression и race доказывают source lifecycle defect, а не причину
каждого большого network timeout. Условие снятия: pinned dependency включает
эквивалентный ACK и тот же regression проходит. Проверять при каждом bump.

Independent reference overlay содержит такой же минимальный ACK fix отдельно
от candidate patches. Helper проверяет чистый pinned checkout, исходный и
исправленный file hashes и создаёт overlay снаружи; reference checkout/module
cache не меняются. Stock-control сборка явно помечена и не подменяет patched
reference evidence. Independent wireguard codec остаётся прежним.

## Codec / protocol

Один transport/awgprofile владеет validation/render/configure для standalone
AWG и embedded Tailscale; старые helpers/testdata перемещены без смены wire
семантики. Profile fingerprint = version + canonical IPC; label и WG identity
в него не входят. Header key в public lab генерируется только из явно
синтетической константы. Numeric singleton H values нормализуются JSON codec в
числа; строка N и число N эквивалентны, диапазон остаётся строкой.

## Engineering evidence и открытые gates

Изолированные direct/DERP TCP/UDP, IPv4/IPv6 payload, rekey/cookie, VLESS
parallel/carrier, profile mismatch/ACL/logout/fail-closed и bounded application
checks уже использовались для engineering implementation. Область каждого
нового прогона фиксируется отдельно; source sync не означает повтор всех
тестов. Plain second endpoint mode isolation не означает проверку его data
plane, если такой запрос фактически не выполнялся.

Android длительная DERP stability, mobile handoff, Windows/macOS native
route/DNS/handoff, iOS Packet Tunnel и publication immutable dependency pin
остаются отдельными gates. Успешные малые запросы, control handshake и source
regression не закрывают их. Личные topology/device/deployment logs исключены.
