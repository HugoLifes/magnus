import 'package:fluent_ui/fluent_ui.dart';
import 'package:flutter/material.dart' show Material;
import 'package:sidebarx/sidebarx.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Windows: FluentApp + barra lateral colapsable (sidebarx)
/// sobre un fondo Acrylic translúcido (glassmorphism). Oscuro por defecto.
class WindowsShell extends StatefulWidget {
  const WindowsShell({super.key, required this.appearance});
  final Appearance appearance;

  @override
  State<WindowsShell> createState() => _WindowsShellState();
}

class _WindowsShellState extends State<WindowsShell> {
  final _controller = SidebarXController(selectedIndex: 0, extended: true);

  @override
  void initState() {
    super.initState();
    _controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(DesignSystem.windows, widget.appearance.brightness);
    final dark = t.isDark;

    return FluentApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: FluentThemeData(
        accentColor: AccentColor.swatch(<String, Color>{
          'normal': t.accent,
          'light': t.accent,
          'dark': t.accent,
        }),
        brightness: widget.appearance.brightness,
        scaffoldBackgroundColor: Colors.transparent,
        micaBackgroundColor: Colors.transparent,
      ),
      home: DecoratedBox(
        decoration: BoxDecoration(gradient: shellBackdrop(t)),
        child: Material(
          color: const Color(0x00000000),
          child: Row(
            children: [
              _Sidebar(controller: _controller, theme: t, dark: dark),
              Expanded(
                child: themedPage(
                    DesignSystem.windows, widget.appearance, _controller.selectedIndex),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.controller, required this.theme, required this.dark});
  final SidebarXController controller;
  final MagnusTheme theme;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return SidebarX(
      controller: controller,
      showToggleButton: true,
      headerBuilder: (context, extended) => ShellBrand(theme: t, extended: extended),
      headerDivider: Container(height: 1, color: t.stroke),
      extendedTheme: SidebarXTheme(
        width: 224,
        decoration: BoxDecoration(
          color: dark ? const Color(0x14FFFFFF) : const Color(0x99FFFFFF),
          border: Border(right: BorderSide(color: t.stroke)),
        ),
        itemPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        selectedItemPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        itemTextPadding: const EdgeInsets.only(left: 14),
        selectedItemTextPadding: const EdgeInsets.only(left: 14),
        textStyle: TextStyle(color: t.textMuted, fontSize: 13.5),
        selectedTextStyle: TextStyle(color: t.text, fontSize: 13.5, fontWeight: FontWeight.w600),
        iconTheme: IconThemeData(color: t.textMuted, size: 20),
        selectedIconTheme: IconThemeData(color: t.accent, size: 20),
        itemDecoration: const BoxDecoration(color: Colors.transparent),
        selectedItemDecoration: BoxDecoration(
          color: t.accentSoft,
          borderRadius: BorderRadius.circular(t.radius),
          border: Border.all(color: t.accent.withValues(alpha: 0.35)),
        ),
      ),
      theme: SidebarXTheme(
        width: 70,
        decoration: BoxDecoration(
          color: dark ? const Color(0x14FFFFFF) : const Color(0x99FFFFFF),
          border: Border(right: BorderSide(color: t.stroke)),
        ),
        itemPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        selectedItemPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        iconTheme: IconThemeData(color: t.textMuted, size: 20),
        selectedIconTheme: IconThemeData(color: t.accent, size: 20),
        itemDecoration: const BoxDecoration(color: Colors.transparent),
        selectedItemDecoration: BoxDecoration(
          color: t.accentSoft,
          borderRadius: BorderRadius.circular(t.radius),
        ),
      ),
      items: [
        for (final d in magnusDestinations)
          SidebarXItem(icon: d.icon, label: d.label),
      ],
    );
  }
}
