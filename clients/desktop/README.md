# Magnus — Cliente de escritorio (Flutter)

Cliente multiplataforma (Windows / macOS / Linux) que consume la **API local del daemon**
de Magnus. Foco actual: **escritorio Windows**. Construido con **clean architecture + BLoC** y
con **3 sistemas de diseño nativos** seleccionables en caliente.

## Diseños (elegibles en Ajustes, sin reiniciar)

| Diseño | Paquete | Shell |
|---|---|---|
| **Windows** | `fluent_ui` + `sidebarx` + `flutter_acrylic` | Fluent/WinUI, sidebar colapsable |
| **Android** | Material 3 (SDK) | `NavigationRail` |
| **Apple** | `macos_ui` | `MacosWindow` + `Sidebar` |

> Cupertino es de iOS; para Apple **de escritorio** se usa `macos_ui`. El contenido de las
> páginas es neutral (widgets de `flutter/widgets`) para verse igual dentro de cualquier shell;
> cada shell aporta su navegación nativa.

## Arquitectura (clean architecture)

```
lib/
├── core/                       # transversal
│   ├── constants.dart          #   URL daemon, presets, cuants, tamaño mín. ventana
│   ├── di/injector.dart        #   get_it: grafo de dependencias
│   ├── network/dio_client.dart #   Dio hacia el daemon
│   ├── error/failures.dart     #   errores de dominio
│   ├── theme/design_system.dart#   enum de los 3 diseños
│   └── responsive/breakpoints.dart # se ajusta al achicar la ventana
├── features/
│   ├── models/                 # feature: gestor de modelos + compatibilidad
│   │   ├── domain/             #   entities, repositorio (abstracto), usecases
│   │   ├── data/               #   dtos, datasource (Dio), repositorio (impl)
│   │   └── presentation/       #   bloc, pages, widgets
│   └── settings/               # feature: diseño + URL del daemon (Cubit + prefs)
├── shell/
│   ├── windows/  material/  apple/   # un shell por diseño
├── app.dart                    # elige el shell según el diseño
└── main.dart                   # DI + window_manager + runApp
```

Flujo de dependencias: `presentation → domain ← data`. La presentación depende de abstracciones
(`MagnusRepository`), nunca de Dio. Los casos de uso aíslan la intención de negocio.

## Estado / datos

- **flutter_bloc**: `ModelsBloc` (hardware, modelos, matriz de cuantizaciones) y `SettingsCubit`
  (diseño + URL daemon, persistidos con `shared_preferences`).
- Endpoints consumidos: `GET /hardware`, `GET /models`, `POST /compatibility`. La matriz de
  cuantizaciones se arma llamando `/compatibility` por cada cuant (hasta que el daemon exponga
  `/quants` — ver `../../docs/ROADMAP.md`).

## Puesta en marcha

Requisitos para compilar **Windows desktop**:
1. **Flutter SDK** (probado en canal stable).
2. **Visual Studio 2022** con la carga de trabajo **"Desktop development with C++"**.
3. **Developer Mode** de Windows activado (los plugins usan symlinks):
   `start ms-settings:developers`

```bash
flutter pub get
flutter run -d windows        # o -d macos / -d linux

# Empaquetar instalador Windows (.msix)
dart run msix:create
```

> El daemon debe estar corriendo: en el server `magnus serve` (por defecto
> `http://127.0.0.1:8420`). Si el cliente corre en otra máquina, ajusta la URL en **Ajustes**
> y publica el puerto del daemon con autenticación/firewall.

## Pendiente (siguientes pasos)

- Pantallas de chat con streaming (WebSocket `/chat`) y dashboard de tokens/coste (`fl_chart`).
- Acción de descarga de modelos (`magnus pull`) cuando el daemon exponga el endpoint.
- Afinar el tema visual por diseño (hoy el contenido usa una paleta neutral).
