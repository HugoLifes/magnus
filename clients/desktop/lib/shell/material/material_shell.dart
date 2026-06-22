import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Android: Material 3 (Material You) + NavigationRail.
/// El rail muestra etiquetas en pantallas anchas y solo iconos al achicar.
class MaterialShell extends StatefulWidget {
  const MaterialShell({super.key, required this.appearance, required this.font});
  final Appearance appearance;
  final String font;

  @override
  State<MaterialShell> createState() => _MaterialShellState();
}

class _MaterialShellState extends State<MaterialShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(
        DesignSystem.material, widget.appearance.brightness,
        font: widget.font);

    return MaterialApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF6750A4),
        useMaterial3: true,
        brightness: widget.appearance.brightness,
        scaffoldBackgroundColor: t.bg,
        textTheme: GoogleFonts.getTextTheme(
          widget.font,
          ThemeData(brightness: widget.appearance.brightness).textTheme,
        ),
        navigationRailTheme: NavigationRailThemeData(
          indicatorShape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
      home: LayoutBuilder(
        builder: (context, constraints) {
          final extended = constraints.maxWidth >= 1040;
          return Scaffold(
            body: DecoratedBox(
              decoration: BoxDecoration(gradient: shellBackdrop(t)),
              child: Row(
                children: [
                  _Rail(theme: t, index: _index, extended: extended,
                      onSelect: (i) => setState(() => _index = i)),
                  Expanded(
                    child: themedPage(DesignSystem.material, widget.appearance,
                        widget.font, _index),
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

class _Rail extends StatelessWidget {
  const _Rail({
    required this.theme,
    required this.index,
    required this.extended,
    required this.onSelect,
  });
  final MagnusTheme theme;
  final int index;
  final bool extended;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return Container(
      decoration: BoxDecoration(
        color: t.surfaceAlt,
        border: Border(right: BorderSide(color: t.stroke)),
      ),
      child: SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: MediaQuery.of(context).size.height),
          child: IntrinsicHeight(
            child: NavigationRail(
              extended: extended,
              backgroundColor: Colors.transparent,
              selectedIndex: index,
              onDestinationSelected: onSelect,
              leading: ShellBrand(theme: t, extended: extended),
              indicatorColor: t.accentSoft,
              selectedIconTheme: IconThemeData(color: t.accent),
              unselectedIconTheme: IconThemeData(color: t.textMuted),
              selectedLabelTextStyle:
                  TextStyle(color: t.text, fontWeight: FontWeight.w600),
              unselectedLabelTextStyle: TextStyle(color: t.textMuted),
              destinations: [
                for (final d in magnusDestinations)
                  NavigationRailDestination(
                      icon: Icon(d.icon), label: Text(d.label)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
