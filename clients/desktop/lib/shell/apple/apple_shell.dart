import 'package:flutter/widgets.dart';
import 'package:macos_ui/macos_ui.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Apple (escritorio): macos_ui con MacosWindow + Sidebar.
/// La sidebar de macos_ui es colapsable y responsive por defecto.
class AppleShell extends StatefulWidget {
  const AppleShell({super.key, required this.appearance, required this.font});
  final Appearance appearance;
  final String font;

  @override
  State<AppleShell> createState() => _AppleShellState();
}

class _AppleShellState extends State<AppleShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(
        DesignSystem.apple, widget.appearance.brightness,
        font: widget.font);
    final macTheme = t.isDark ? MacosThemeData.dark() : MacosThemeData.light();

    return MacosApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: macTheme,
      home: MacosWindow(
        sidebar: Sidebar(
          minWidth: 224,
          top: ShellBrand(theme: t, extended: true),
          builder: (context, scrollController) => SidebarItems(
            currentIndex: _index,
            scrollController: scrollController,
            selectedColor: t.accentSoft,
            unselectedColor: const Color(0x00000000),
            itemSize: SidebarItemSize.large,
            onChanged: (i) => setState(() => _index = i),
            items: [
              for (final d in magnusDestinations)
                SidebarItem(
                  leading: MacosIcon(d.icon),
                  label: Text(d.label),
                ),
            ],
          ),
        ),
        child: MacosScaffold(
          toolBar: ToolBar(
            title: Text(magnusDestinations[_index].label),
            titleWidth: 250,
          ),
          children: [
            ContentArea(
              builder: (context, scrollController) => DecoratedBox(
                decoration: BoxDecoration(gradient: shellBackdrop(t)),
                child: themedPage(
                    DesignSystem.apple, widget.appearance, widget.font, _index),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
