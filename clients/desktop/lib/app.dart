import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'core/di/injector.dart';
import 'core/theme/design_system.dart';
import 'core/theme/icons.dart';
import 'core/theme/magnus_theme.dart';
import 'features/agents/presentation/cubit/agents_cubit.dart';
import 'features/agents/presentation/pages/agents_page.dart';
import 'features/chat/presentation/cubit/chat_cubit.dart';
import 'features/chat/presentation/pages/chat_page.dart';
import 'features/cloud/presentation/cubit/cloud_cubit.dart';
import 'features/cloud/presentation/pages/cloud_page.dart';
import 'features/models/presentation/bloc/models_bloc.dart';
import 'features/models/presentation/cubit/catalog_cubit.dart';
import 'features/models/presentation/cubit/overview_cubit.dart';
import 'features/models/presentation/pages/dashboard_page.dart';
import 'features/models/presentation/pages/models_page.dart';
import 'features/rag/presentation/cubit/rag_cubit.dart';
import 'features/rag/presentation/pages/rag_page.dart';
import 'features/resources/presentation/pages/resources_page.dart';
import 'features/settings/presentation/cubit/settings_cubit.dart';
import 'features/settings/presentation/pages/settings_page.dart';
import 'shell/apple/apple_shell.dart';
import 'shell/material/material_shell.dart';
import 'shell/windows/windows_shell.dart';

/// Destinos de navegación, compartidos por los 3 shells.
///
/// Cada destino dice *qué* icono quiere, no *cuál*: el shell lo resuelve con
/// el set de su plataforma (Fluent, Material o SF).
class NavDest {
  const NavDest(this.label, this._icon);
  final String label;
  final IconData Function(MagnusIcons) _icon;

  IconData iconFor(DesignSystem design) => _icon(MagnusIcons.forDesign(design));
}

/// Páginas, indexadas igual que [magnusDestinations].
Widget magnusPage(int index) => switch (index) {
      0 => const DashboardPage(),
      1 => const ChatPage(),
      2 => const ModelsPage(),
      3 => const AgentsPage(),
      4 => const RagPage(),
      5 => const ResourcesPage(),
      6 => const CloudPage(),
      _ => const SettingsPage(),
    };

final magnusDestinations = <NavDest>[
  NavDest('Inicio', (i) => i.dashboard),
  NavDest('Chat', (i) => i.chat),
  NavDest('Modelos', (i) => i.models),
  NavDest('Agentes', (i) => i.agents),
  NavDest('Documentos', (i) => i.documents),
  NavDest('Recursos', (i) => i.resources),
  NavDest('Nube', (i) => i.cloud),
  NavDest('Ajustes', (i) => i.settings),
];

/// Página con la que abre la app: `--pagina=chat` (o `modelos`, `nube`…).
/// Sirve para accesos directos que llevan directo a una sección.
int startPageFrom(List<String> args) {
  for (final a in args) {
    if (!a.startsWith('--pagina=')) continue;
    final wanted = _plain(a.substring('--pagina='.length));
    final i = magnusDestinations.indexWhere((d) => _plain(d.label) == wanted);
    if (i >= 0) return i;
  }
  return 0;
}

String _plain(String s) => s
    .toLowerCase()
    .replaceAll('á', 'a')
    .replaceAll('é', 'e')
    .replaceAll('í', 'i')
    .replaceAll('ó', 'o')
    .replaceAll('ú', 'u');

/// Raíz de la app. Provee los BLoC por encima del *App y elige el shell según
/// el diseño elegido. Reconstruye al cambiar diseño o apariencia.
class MagnusApp extends StatelessWidget {
  const MagnusApp({super.key, this.systemAccent, this.initialPage = 0});

  /// Acento del sistema operativo (si está disponible), para M3/Fluent.
  final Color? systemAccent;

  /// Índice en [magnusDestinations] de la página inicial.
  final int initialPage;

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider<SettingsCubit>.value(value: sl<SettingsCubit>()),
        BlocProvider<ModelsBloc>(
          create: (_) => sl<ModelsBloc>()..add(const HardwareRequested()),
        ),
        BlocProvider<OverviewCubit>.value(value: sl<OverviewCubit>()..load()),
        BlocProvider<ChatCubit>.value(value: sl<ChatCubit>()),
        BlocProvider<CatalogCubit>.value(value: sl<CatalogCubit>()),
        BlocProvider<RagCubit>.value(value: sl<RagCubit>()),
        BlocProvider<AgentsCubit>.value(value: sl<AgentsCubit>()),
        BlocProvider<CloudCubit>.value(value: sl<CloudCubit>()),
      ],
      child: BlocBuilder<SettingsCubit, SettingsState>(
        buildWhen: (a, b) =>
            a.design != b.design ||
            a.appearance != b.appearance ||
            a.fontFamily != b.fontFamily ||
            a.useSystemAccent != b.useSystemAccent,
        builder: (context, state) {
          final appearance = state.appearance;
          final font = state.fontFamily;
          final accent = state.useSystemAccent ? systemAccent : null;
          return switch (state.design) {
            DesignSystem.windows => WindowsShell(
                appearance: appearance, font: font, accent: accent, initialPage: initialPage),
            DesignSystem.material => MaterialShell(
                appearance: appearance, font: font, accent: accent, initialPage: initialPage),
            DesignSystem.apple => AppleShell(
                appearance: appearance, font: font, accent: accent, initialPage: initialPage),
          };
        },
      ),
    );
  }
}

/// Helper para que cada shell envuelva la página activa con el [MagnusTheme]
/// correspondiente a su diseño, apariencia, fuente y acento.
Widget themedPage(DesignSystem design, Appearance appearance, String font,
    Color? accent, int index) {
  return MagnusTheme.forDesign(design, appearance.brightness,
          font: font, accent: accent)
      .provide(child: magnusPage(index));
}
