import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'core/di/injector.dart';
import 'core/theme/design_system.dart';
import 'core/theme/magnus_theme.dart';
import 'features/models/presentation/bloc/models_bloc.dart';
import 'features/models/presentation/pages/dashboard_page.dart';
import 'features/models/presentation/pages/models_page.dart';
import 'features/chat/presentation/pages/chat_page.dart';
import 'features/rag/presentation/pages/rag_page.dart';
import 'features/resources/presentation/pages/resources_page.dart';
import 'features/settings/presentation/cubit/settings_cubit.dart';
import 'features/settings/presentation/pages/settings_page.dart';
import 'shell/apple/apple_shell.dart';
import 'shell/material/material_shell.dart';
import 'shell/windows/windows_shell.dart';

/// Destinos de navegación, compartidos por los 3 shells.
class NavDest {
  const NavDest(this.label, this.icon);
  final String label;
  final IconData icon; // IconData de MaterialIcons, estable entre shells.
}

/// Páginas, indexadas igual que [magnusDestinations].
Widget magnusPage(int index) => switch (index) {
      0 => const DashboardPage(),
      1 => const ChatPage(),
      2 => const ModelsPage(),
      3 => const RagPage(),
      4 => const ResourcesPage(),
      _ => const SettingsPage(),
    };

const magnusDestinations = <NavDest>[
  NavDest('Inicio', LucideIcons.gauge),
  NavDest('Chat', LucideIcons.messageCircle),
  NavDest('Modelos', LucideIcons.cpu),
  NavDest('RAG', LucideIcons.brain),
  NavDest('Recursos', LucideIcons.heartPulse),
  NavDest('Ajustes', LucideIcons.settings),
];

/// Raíz de la app. Provee los BLoC por encima del *App y elige el shell según
/// el diseño elegido. Reconstruye al cambiar diseño o apariencia.
class MagnusApp extends StatelessWidget {
  const MagnusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider<SettingsCubit>.value(value: sl<SettingsCubit>()),
        BlocProvider<ModelsBloc>(
          create: (_) => sl<ModelsBloc>()..add(const HardwareRequested()),
        ),
      ],
      child: BlocBuilder<SettingsCubit, SettingsState>(
        buildWhen: (a, b) =>
            a.design != b.design ||
            a.appearance != b.appearance ||
            a.fontFamily != b.fontFamily,
        builder: (context, state) {
          final appearance = state.appearance;
          final font = state.fontFamily;
          return switch (state.design) {
            DesignSystem.windows =>
              WindowsShell(appearance: appearance, font: font),
            DesignSystem.material =>
              MaterialShell(appearance: appearance, font: font),
            DesignSystem.apple => AppleShell(appearance: appearance, font: font),
          };
        },
      ),
    );
  }
}

/// Helper para que cada shell envuelva la página activa con el [MagnusTheme]
/// correspondiente a su diseño, apariencia y fuente.
Widget themedPage(
    DesignSystem design, Appearance appearance, String font, int index) {
  return MagnusTheme.forDesign(design, appearance.brightness, font: font)
      .provide(child: magnusPage(index));
}
