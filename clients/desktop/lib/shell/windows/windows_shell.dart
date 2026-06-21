import 'package:fluent_ui/fluent_ui.dart';
import 'package:flutter/material.dart' show Material;
import 'package:sidebarx/sidebarx.dart';

import '../../app.dart';

/// Shell de diseño Windows: FluentApp + barra lateral colapsable (sidebarx).
/// La sidebar se contrae a solo iconos al achicar la ventana (responsive).
class WindowsShell extends StatefulWidget {
  const WindowsShell({super.key});
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
    return FluentApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: FluentThemeData(accentColor: Colors.purple, brightness: Brightness.light),
      home: ScaffoldPage(
        padding: EdgeInsets.zero,
        content: Row(
          children: [
            // Material transparente para que sidebarx tenga su ancestro.
            Material(
              color: const Color(0x00000000),
              child: SidebarX(
                controller: _controller,
                showToggleButton: true,
                extendedTheme: const SidebarXTheme(width: 220),
                theme: const SidebarXTheme(
                  width: 64,
                  itemTextPadding: EdgeInsets.only(left: 12),
                  selectedItemTextPadding: EdgeInsets.only(left: 12),
                ),
                items: [
                  for (final d in magnusDestinations)
                    SidebarXItem(icon: d.icon, label: d.label),
                ],
              ),
            ),
            Expanded(child: magnusPage(_controller.selectedIndex)),
          ],
        ),
      ),
    );
  }
}
