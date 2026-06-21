import 'package:flutter/widgets.dart';
import 'package:macos_ui/macos_ui.dart';

import '../../app.dart';

/// Shell de diseño Apple (escritorio): macos_ui con MacosWindow + Sidebar.
/// La sidebar de macos_ui es colapsable y responsive por defecto.
class AppleShell extends StatefulWidget {
  const AppleShell({super.key});
  @override
  State<AppleShell> createState() => _AppleShellState();
}

class _AppleShellState extends State<AppleShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return MacosApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: MacosThemeData.light(),
      home: MacosWindow(
        sidebar: Sidebar(
          minWidth: 200,
          builder: (context, scrollController) => SidebarItems(
            currentIndex: _index,
            scrollController: scrollController,
            onChanged: (i) => setState(() => _index = i),
            items: [
              for (final d in magnusDestinations)
                SidebarItem(leading: MacosIcon(d.icon), label: Text(d.label)),
            ],
          ),
        ),
        child: MacosScaffold(
          children: [
            ContentArea(builder: (context, scrollController) => magnusPage(_index)),
          ],
        ),
      ),
    );
  }
}
