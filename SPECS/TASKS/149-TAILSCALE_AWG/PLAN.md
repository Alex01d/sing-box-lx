# PLAN: 149 — TAILSCALE_AWG

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).

## Подготовка публичного вклада

Сохранить private backup до синхронизации и редактирования. Обновить текущую
ветку обычным fast-forward/merge, сохранить незакоммиченные изменения и не
переписывать историю. При занятом upstream номере задачи перенумеровать только
неопубликованную AWG-задачу; опубликованная 148 относится к OOM runtime memory.

Публичная дельта включает reusable core implementation, shared codec refactor,
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
4. Использовать общий transport/awgprofile для validate/render/configure,
   оставить standalone WireGuard адаптер тонким. Новая подсистема изолирована
   build tag with_tailscale_awg; неполная capability отклоняет профиль явно.
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

## CI сохранность shared codec regressions

При переносе AWG helpers/tests в transport/awgprofile добавить новый пакет в
существующие lx-ci vet и AWG test lists, сохраняя прежние transport/wireguard
checks. Новый Tailscale DNS regression запускать по имени с default capability
tags; этот source-level gate не требует external AWG dependency workspace.
