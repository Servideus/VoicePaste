# Зависимости и распространение

Исходный код VoicePaste распространяется по MIT. Это не меняет лицензии зависимостей. Версии зафиксированы в `requirements-lock.txt`; тексты из установленных пакетов собраны в `third_party_licenses/`, список — `PACKAGES.txt`. Сборочные инструменты также указаны в этом списке, хотя не все входят в приложение.

PySide6, Shiboken6 и Qt 6.10.2 имеют отдельные условия Qt. Для открытого распространения применимы соответствующие лицензии LGPL/GPL, а коммерческий вариант требует отдельной лицензии. См. [обязательства LGPL от Qt](https://www.qt.io/development/open-source-lgpl-obligations). В комплект добавлены LGPL 3 и GPL 3 из официального репозитория Qt.

Точные исходники библиотек доступны у разработчика:

- [Qt 6.10.2](https://download.qt.io/official_releases/qt/6.10/6.10.2/single/).
- [PySide6 / Shiboken6 6.10.2](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/).

Qt загружается как динамические DLL; PyInstaller извлекает их при запуске однофайловой сборки. Исходники приложения и инструкция сборки позволяют пересобрать приложение с заменённой совместимой библиотекой. В публичном релизе исходники приложения, spec, lock-файл и инструкции сборки доступны в том же репозитории. Соответствующие исходники немодифицированных Qt и PySide6/Shiboken6 доступны по ссылкам ниже. Тексты лицензий включены в репозиторий и архив релиза.

Windows предоставляет системные ICU и UCRT. Spec исключает их случайные копии из сторонних каталогов PATH, которые могут нарушить запуск Qt.

## Corresponding sources and rebuilding

VoicePaste application source and build scripts: https://github.com/Servideus/VoicePaste/tree/v1.1.5-beta

- Qt 6.10.2 source: https://download.qt.io/official_releases/qt/6.10/6.10.2/single/qt-everywhere-src-6.10.2.tar.xz
- PySide6 and Shiboken6 6.10.2 source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/pyside-setup-everywhere-src-6.10.2.tar.xz
- Qt license texts: third_party_licenses/LGPL-3.0-only.txt and GPL-3.0-only.txt.

To rebuild with a modified compatible Qt/PySide6 library, follow the source installation instructions in README.md, install the replacement build in the virtual environment, and run build.ps1. Update the pinned dependency requirements if the replacement has a different version. VoicePaste imposes no restriction on modification or reverse engineering for debugging modifications to LGPL libraries. No changes to Qt/PySide6 source are included in this release.