import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/icons.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Android: Material 3 (Material You) + NavigationRail.
/// El rail muestra etiquetas en pantallas anchas y solo iconos al achicar.
class MaterialShell extends StatefulWidget {
  const MaterialShell({
    super.key,
    required this.appearance,
    required this.font,
    this.accent,
    this.initialPage = 0,
  });
  final Appearance appearance;
  final String font;
  final Color? accent;
  final int initialPage;

  @override
  State<MaterialShell> createState() => _MaterialShellState();
}

class _MaterialShellState extends State<MaterialShell> {
  late int _index = widget.initialPage;

  /// Plegado a mano. Null: lo decide el ancho de la ventana, que es lo que
  /// espera Material; en cuanto la persona toca el botón, manda ella.
  bool? _extended;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(
        DesignSystem.material, widget.appearance.brightness,
        font: widget.font, accent: widget.accent);

    return MaterialApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: widget.accent ?? const Color(0xFF6750A4),
        useMaterial3: true,
        brightness: widget.appearance.brightness,
        scaffoldBackgroundColor: t.bg,
        textTheme: GoogleFonts.getTextTheme(
          widget.font,
          ThemeData(brightness: widget.appearance.brightness).textTheme,
        ),
        // Material 3: el indicador del rail es una píldora (StadiumBorder).
        navigationRailTheme: const NavigationRailThemeData(
          indicatorShape: StadiumBorder(),
        ),
      ),
      home: LayoutBuilder(
        builder: (context, constraints) {
          final extended = _extended ?? constraints.maxWidth >= 1040;
          return Scaffold(
            body: ShellBackdrop(
              theme: t,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Rail(
                    theme: t,
                    index: _index,
                    extended: extended,
                    onSelect: (i) => setState(() => _index = i),
                    onToggle: () => setState(() => _extended = !extended),
                  ),
                  Expanded(
                    child: themedPage(DesignSystem.material, widget.appearance,
                        widget.font, widget.accent, _index),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Rail de Material 3: superficie tonal, píldora de indicador y etiquetas
/// siempre visibles (en M3 el rail compacto también rotula sus destinos).
class _Rail extends StatelessWidget {
  const _Rail({
    required this.theme,
    required this.index,
    required this.extended,
    required this.onSelect,
    required this.onToggle,
  });
  final MagnusTheme theme;
  final int index;
  final bool extended;
  final ValueChanged<int> onSelect;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 10, 0, 10),
      decoration: BoxDecoration(
        color: t.bgElevated,
        borderRadius: BorderRadius.circular(t.radiusLg),
      ),
      clipBehavior: Clip.antiAlias,
      child: SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: MediaQuery.of(context).size.height - 20),
          child: IntrinsicHeight(
            child: NavigationRail(
              extended: extended,
              minExtendedWidth: 232,
              labelType: extended ? NavigationRailLabelType.none : NavigationRailLabelType.all,
              backgroundColor: Colors.transparent,
              selectedIndex: index,
              onDestinationSelected: onSelect,
              leading: ShellBrand(theme: t, extended: extended),
              trailing: Padding(
                padding: const EdgeInsets.only(top: 10),
                child: SidebarToggle(theme: t, expanded: extended, onTap: onToggle),
              ),
              indicatorColor: t.accentSoft,
              selectedIconTheme: IconThemeData(color: t.accent, size: 22),
              unselectedIconTheme: IconThemeData(color: t.textMuted, size: 22),
              selectedLabelTextStyle: TextStyle(
                  color: t.text, fontWeight: FontWeight.w700, fontSize: extended ? 14 : 12),
              unselectedLabelTextStyle: TextStyle(
                  color: t.textMuted, fontWeight: FontWeight.w500, fontSize: extended ? 14 : 12),
              destinations: [
                for (final d in magnusDestinations)
                  NavigationRailDestination(
                    icon: Icon(const MagnusIcons.forDesign(DesignSystem.material)
                        .unselected(d.iconFor(DesignSystem.material))),
                    selectedIcon: Icon(d.iconFor(DesignSystem.material)),
                    label: Text(d.label),
                    padding: const EdgeInsets.symmetric(vertical: 2),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
