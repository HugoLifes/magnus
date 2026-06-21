import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'core/di/injector.dart';
import 'core/theme/design_system.dart';
import 'features/models/presentation/bloc/models_bloc.dart';
import 'features/models/presentation/pages/dashboard_page.dart';
import 'features/models/presentation/pages/models_page.dart';
import 'features/settings/presentation/cubit/settings_cubit.dart';
import 'features/settings/presentation/pages/settings_page.dart';
import 'shell/apple/apple_shell.dart';
import 'shell/material/material_shell.dart';
import 'shell/windows/windows_shell.dart';

/// Destinos de navegación, compartidos por los 3 shells.
class NavDest {
  const NavDest(this.label, this.icon);
  final String label;
  // IconData de MaterialIcons (incluida por `uses-material-design: true`),
  // estable entre los tres shells.
  final IconData icon;
}

/// Páginas, indexadas igual que [magnusDestinations].
Widget magnusPage(int index) => switch (index) {
      0 => const DashboardPage(),
      1 => const ModelsPage(),
      _ => const SettingsPage(),
    };

const magnusDestinations = <NavDest>[
  NavDest('Inicio', IconData(0xe1af, fontFamily: 'MaterialIcons')), // space_dashboard
  NavDest('Modelos', IconData(0xe322, fontFamily: 'MaterialIcons')), // memory
  NavDest('Ajustes', IconData(0xe57f, fontFamily: 'MaterialIcons')), // settings
];

/// Raíz de la app. Provee los BLoC por encima del *App y elige el shell según
/// el diseño seleccionado. Cambiar de diseño re-renderiza todo el árbol.
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
        buildWhen: (a, b) => a.design != b.design,
        builder: (context, state) => switch (state.design) {
          DesignSystem.windows => const WindowsShell(),
          DesignSystem.material => const MaterialShell(),
          DesignSystem.apple => const AppleShell(),
        },
      ),
    );
  }
}
