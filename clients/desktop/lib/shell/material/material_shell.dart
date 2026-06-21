import 'package:flutter/material.dart';

import '../../app.dart';

/// Shell de diseño Android: Material 3 + NavigationRail.
/// El rail muestra etiquetas en pantallas anchas y solo iconos al achicar.
class MaterialShell extends StatefulWidget {
  const MaterialShell({super.key});
  @override
  State<MaterialShell> createState() => _MaterialShellState();
}

class _MaterialShellState extends State<MaterialShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF534AB7),
        useMaterial3: true,
        brightness: Brightness.light,
      ),
      home: LayoutBuilder(
        builder: (context, constraints) {
          final extended = constraints.maxWidth >= 1000;
          return Scaffold(
            body: Row(
              children: [
                NavigationRail(
                  extended: extended,
                  selectedIndex: _index,
                  onDestinationSelected: (i) => setState(() => _index = i),
                  destinations: [
                    for (final d in magnusDestinations)
                      NavigationRailDestination(icon: Icon(d.icon), label: Text(d.label)),
                  ],
                ),
                const VerticalDivider(width: 1),
                Expanded(child: magnusPage(_index)),
              ],
            ),
          );
        },
      ),
    );
  }
}
