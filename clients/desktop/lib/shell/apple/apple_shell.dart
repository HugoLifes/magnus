import 'package:flutter/widgets.dart';
import 'package:macos_ui/macos_ui.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Apple (escritorio): macos_ui con MacosWindow + Sidebar.
/// La sidebar de macos_ui es colapsable y responsive por defecto.
class AppleShell extends StatefulWidget {
  const AppleShell({super.key, required this.appearance});
  final Appearance appearance;

  @override
  State<AppleShell> createState() => _AppleShellState();
}

class _AppleShellState extends State<AppleShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(
        DesignSystem.apple, widget.appearance.brightness);
    final macTheme = t.isDark ? MacosThemeData.dark() : MacosThemeData.light();

    return MacosApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: macTheme,
      home: MacosWindow(
        sidebar: Sidebar(
          minWidth: 214,
          top: ShellBrand(theme: t, extended: true),
          builder: (context, scrollController) => SidebarItems(
            currentIndex: _index,
            scrollController: scrollController,
            selectedColor: t.accentSoft,
            unselectedColor: const Color(0x00000000),
            onChanged: (i) => setState(() => _index = i),
            items: [
              for (final d in magnusDestinations)
                SidebarItem(leading: MacosIcon(d.icon), label: Text(d.label)),
            ],
          ),
        ),
        child: MacosScaffold(
          children: [
            ContentArea(
              builder: (context, scrollController) => DecoratedBox(
                decoration: BoxDecoration(gradient: shellBackdrop(t)),
                child: themedPage(DesignSystem.apple, widget.appearance, _index),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
