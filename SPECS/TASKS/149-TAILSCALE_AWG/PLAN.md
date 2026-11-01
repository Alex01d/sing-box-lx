# PLAN: 149 — TAILSCALE_AWG

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).

## Подготовка публичного вклада

Сохранить private backup до синхронизации и редактирования. Обновить текущую
ветку обычным fast-forward/merge, сохранить незакоммиченные изменения и не
переписывать историю. При занятом upstream номере задачи перенумеровать только
неопубликованную AWG-задачу; опубликованная 148 относится к OOM runtime memory.

Публичная дельта включает reusable core implementation, WireGuard-owned codec,
protobuf sources/artifacts, minimal pinned dependency patches, isolated lab,
технические specifications и инструкции для проверки. Удалить из новых docs
личные endpoints, сведения об устройствах/инфраструктуре, локальные пути,
реальные identity/profile data и журналы развёртывания. Сохранить оригиналы
только во внешнем private backup; не добавлять runtime files, binaries или
сырой field evidence. Синтетические fixtures явно обозначать.

После incoming protobuf изменений регенерировать daemon stubs из источника,
сохраняя Tailscale transport field17, WG session fields6/7 и runtime memory10.
Генератор сохраняет современный emptypb import независимо от системного include.
Не форматировать посторонние исходники; launcher получает byte-identical stubs.

## Порядок реализации и проверки

1. Закрепить SagerNet Tailscale base, wireguard-go/gitlinks и независимый peer.
   Сохранить dependency patches с SHA256 в dependencies.json и протестировать
   patch application в новом внешнем workspace. Default/release builds остаются
   на прежней зависимости: engineering AWG opt-in требует внешний go.work.
2. Проверить security backports и explicit restrictions (Serve guards,
   отключённые AWG peer relay и embedded SSH). Не публиковать новый release pin
   до отдельного immutable dependency artifact и полного security gate.
3. Применять typed profile к per-device initializer после cleanup registration,
   до Up/первого пакета. Сохранить headroom8, scoped monitor/carrier lifecycle,
   profile isolation, rekey/reload и обычное поведение без AWG.
4. Сохранить AWG codec/helpers/tests/testdata на исходных путях transport/wireguard.
   protocol/tailscale напрямую импортирует этот пакет через узкий typed API
   CompileTailscaleAWGProfile/TailscaleAWGProfile.Apply. Raw IPC и старые helpers
   остаются private; новой общей package boundary нет. Build tag with_tailscale_awg
   и отказ при неполной capability сохраняются.
5. Добавить optional status через существующий adapter/protobuf/libbox путь.
   Не включать секреты в fingerprint/status/errors и не считать control login
   или DISCO ping доказательством data plane.
6. Проверить direct/DERP двусторонними TCP/UDP и checksum; private routing/DNS,
   VLESS parallel и carrier; failure paths, lifecycle и два endpoints.
7. Проверить core build, named profile/DNS/tag/status regressions и Python lab
   helpers. Полный platform/consumer CI и ручная приёмка выполняются отдельно.

## Этапы потребителей

Linux engineering → Android engineering → macOS/Windows → iOS Packet Tunnel.
Потребители синхронизируют shared contract и требуют capability до удаления
unsupported полей/узлов. Static CIDR/DNS protection живёт независимо от login
и live routes. Export/backup не переносит machine identity.

Публичная ветка предназначена для командной проверки. Изолированные direct/DERP
и bounded прикладные проверки не закрывают длительную Android DERP stability,
mobile handoff, Windows/macOS DNS/route/handoff или iOS integration. Все эти
незавершённые gates отражаются в TASKS.md и issue вместо утверждения о релизе.

## Проверка прямого WireGuard импорта и upstream/testing

До изменения кода сохранить исходный snapshot. Вернуть ранее перемещённые
AWG helpers/tests/fixtures на исходные пути, сохранив standalone bytes и tags.
Удалить package transport/awgprofile и делегирующий adapter. Tailscale-specific
profile validator размещается в новом tailscale_awg_lx.go внутри transport/wireguard;
экспортируются только typed compiler и immutable profile с Apply. Непроверенный
IPC не становится public API. Существующие CI WireGuard package lists вновь
покрывают codec tests без отдельного нового пакета; DNS regression сохраняется.

Проверить import graph и named regressions с/без with_awg и with_gvisor,
обычный Tailscale и полный opt-in AWG CLI через pinned external go.work.
Не менять protocol/schema/protobuf, dependency patch bytes, submodule pins,
потребителей или работающие VPN.

Отдельно прочитать закреплённый SagerNet/sing-box upstream/testing и его
sing-tun/Tailscale pins. В PORTING_1_15.md перечислить фактические изменения
stack/build tags/API и обязательную адаптацию AWG/Tailscale. Это compatibility
audit, а не merge/testing port или обещание готовности1.15. История прежней
package boundary переносится в HISTORY.md.
