# Изолированный Linux стенд AWG/Tailscale

Не запускает host TUN, системный tailscaled или установленный sing-box.
Docker network/containers имеют label org.leadaxe.spec=143-tailscale-awg.
Root/CAP_NET_ADMIN используется только внутри выделенных контейнеров.
Нужны Linux, Docker, iproute2, Python 3, OpenSSL и Go toolchain download access.

## Новый стенд

Из core checkout с закреплёнными submodules:

```sh
python3 lx-test/tailscale-awg/build_lab.py --workspace /absolute/new/awg-lab
python3 lx-test/tailscale-awg/lab.py --root /absolute/new/awg-lab/lab --binaries /absolute/new/awg-lab --mode all
python3 lx-test/tailscale-awg/core_lab.py --root /absolute/new/awg-lab/lab --binaries /absolute/new/awg-lab
```

build_lab.py клонирует exact reference pin, не меняя его файлы; reference
adapter и отдельный reference Go overlay создаются снаружи. По умолчанию
reference получает только описанный ниже ACK backport. Кандидат использует внешний go.work, base+SHA256
patch из dependencies.json, существующие core submodule pins. Default core
build и production pin не меняются. Для portable CLI:

```sh
GOWORK=/absolute/new/awg-lab/dependency/go.work GOTOOLCHAIN=go1.26.10 make -f Makefile.lx lx-build LX_TAILSCALE_AWG=1 LX_VERSION=1.14.4-lx.29-awg149.dev LX_OUTPUT=/absolute/new/awg-lab/sing-box
```

## Независимый reference: исправленный стенд и stock control

Reference остаётся закреплённым LiuTangLei Tailscale `f58b730…` с независимым
WireGuard `v0.0.34`. В его старом `receiveDERP` при закрытии bind терялся ACK
заимствованного результата; reader ожидал его перед следующим кадром.
Детерминированный тест дал RED на исходнике, GREEN10 и race-GREEN10 после
трёхстрочного nil-guarded `copyBuf(nil)` перед существующим `break`.
Это подтверждённый дефект исходника, но не доказанная причина каждого
физического AWG2/DERP timeout.

`reference_overlay.py` проверяет HEAD, чистоту checkout, SHA256 исходного
`wgengine/magicsock/derp.go`, отдельного patch/test и точные исправленные байты.
Он создаёт исправленную копию, production/test Go overlays и metadata только
в новом внешнем каталоге. Ни reference checkout, ни Go module cache не патчатся.
Пины лежат в `dependencies.json → reference.patch`, отдельно от `patches`
кандидата. Четыре общих AWG seams кандидата, его существующие carrier/security
seams и независимый WG0.34 не меняются; wire format, профили, очереди и timeout
этот backport не меняет. Production/release pins остаются прежними.

По умолчанию `build_lab.py` собирает reference через production overlay и пишет
его режим, команду, SHA256 бинаря и patch в `reference-build.json`.
Для явно неисправленного контрольного peer нужен отдельный новый workspace:

```sh
python3 lx-test/tailscale-awg/build_lab.py --workspace /absolute/new/awg-lab-stock --stock-reference
```

Такой артефакт помечен `stock-control`, `patch_applied=false`, без production
overlay. Он не подменяет результаты прежних stock-прогонов. Физическая
совместимость нового peer и причина сетевого сбоя проверяются отдельно;
успешный локальный source gate не является data-plane приёмкой.

Фокусированные offline-проверки helper читают чистый pinned checkout, создавая
все результаты во временных внешних каталогах:

```sh
python3 lx-test/tailscale-awg/test_reference_overlay.py --checkout /absolute/pinned/reference -v
python3 lx-test/tailscale-awg/reference_overlay.py --checkout /absolute/pinned/reference --output /absolute/new/reference-overlay
```

Полученный `go-test-overlay.json` добавляет точный regression из `.go.txt`,
не записывая его в reference. В pinned checkout можно повторить только этот
gate с Go1.27.3, `GOWORK=off`, `-mod=readonly`, `-overlay=.../go-test-overlay.json`,
пакетом `./wgengine/magicsock` и `-run '^TestDERPReceiveBindClose' -count=10`
(отдельно `-race`). Helper с `--stock-reference` создаёт test-only overlay для
ожидаемого RED. Снимать backport нужно при pin на upstream с эквивалентным ACK
и прошедшим этим Close/Open/race gate; при каждом bump перепроверять base/hash.

G0 проверяет 24 комбинации plain/AWG2/AWG3 × IPv4/IPv6 × direct/DERP × два
направления. На каждую — двусторонний TCP 16 MiB+SHA256 и UDP echo.
core_lab.py проверяет subnet/DNS guards, VLESS parallel/carrier, API/status и
существующий StartConnectionTest. Файл launcher_lab.py принимает настоящий
launcher-generated config в strict JSON и проверяет его отдельно. При
необходимости удалить комментарии только из сгенерированного test config;
profile/route/DNS решения не подменять ручными эквивалентами.

Synthetic private services 10.77.1.203/100.64.0.10 живут только на loopback router
контейнера, IPv6 payload проходит через IPv4 underlay. Docker network internal,
публичного ingress нет, TLS проверяется штатно. Lab CA доверяется только
контейнерам/процессам тестового bundle; в OS trust store не устанавливается.
Секретные pre-auth keys/state — только во внешнем root, не в исходниках.

## Повтор и очистка

G0 runner переиспользует свои running containers. Для повторного full-core
прогона удалить только lx-awg-143-core-client и lx-awg-143-core-router после
проверки label (identity хранится во внешнем root). Для launcher runner —
аналогично lx-awg-143-launcher-client. При прерванном прогоне не считать
недописанный JSON или Running control plane успешной приёмкой.

Полная очистка только ресурсов этой задачи:

```sh
python3 lx-test/tailscale-awg/lab.py --root /absolute/new/awg-lab/lab --binaries /absolute/new/awg-lab --stop
```

Не использовать docker prune, host firewall/sysctl или process-name kill.
Ни один runner не публикует релиз и не меняет внешние Headscale environments.

Дополнительные gates (с тем же GOWORK/GOTOOLCHAIN): rekey_lab.py ждёт 130s
и проверяет новый handshake + TCP/UDP без restart; cookie_gate.py добавляет
synthetic test через go -overlay, не редактируя gitlink checkout.
launcher_lab.py --carrier-env auto|derp создаёт отдельные контейнеры с
недоступным ambient HTTPS_PROXY и проверяет приоритет explicit carrier.
