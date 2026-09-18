import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb;
import 'package:flutter/widgets.dart';
import 'package:macos_ui/macos_ui.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Apple (escritorio): macos_ui con MacosWindow + Sidebar.
///
/// En macOS la barra lateral es la nativa de macos_ui, con vibrancy. Fuera de
/// macOS se usa una réplica: macos_ui borra esa zona (`BlendMode.clear`) para
/// que macOS pinte su material translúcido, y en Windows o Linux eso deja un
/// hueco negro que ningún color puede tapar.
class AppleShell extends StatefulWidget {
  const AppleShell({
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
  State<AppleShell> createState() => _AppleShellState();
}

class _AppleShellState extends State<AppleShell> {
  late int _index = widget.initialPage;

  /// Ajustes es el último destino y vive en el pie, como en Música o Notas.
  static final _settings = magnusDestinations.length - 1;

  void _select(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.forDesign(
        DesignSystem.apple, widget.appearance.brightness,
        font: widget.font, accent: widget.accent);
    final macTheme = (t.isDark ? MacosThemeData.dark() : MacosThemeData.light())
        .copyWith(primaryColor: t.accent);
    final native = !kIsWeb && defaultTargetPlatform == TargetPlatform.macOS;

    final scaffold = MacosScaffold(
      backgroundColor: t.bg,
      toolBar: ToolBar(
        decoration: BoxDecoration(
          color: t.bgElevated,
          border: Border(bottom: BorderSide(color: t.stroke)),
        ),
        title: Text(magnusDestinations[_index].label,
            style: TextStyle(color: t.text, fontWeight: FontWeight.w600)),
        titleWidth: 250,
      ),
      children: [
        ContentArea(
          builder: (context, scrollController) => ShellBackdrop(
            theme: t,
            child: themedPage(
                DesignSystem.apple, widget.appearance, widget.font, widget.accent, _index),
          ),
        ),
      ],
    );

    return MacosApp(
      title: 'Magnus',
      debugShowCheckedModeBanner: false,
      theme: macTheme,
      home: MacosWindow(
        backgroundColor: t.bg,
        sidebar: native ? _nativeSidebar(t) : null,
        child: native
            ? scaffold
            : Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _ReplicaSidebar(theme: t, index: _index, onSelect: _select),
                  Expanded(child: scaffold),
                ],
              ),
      ),
    );
  }

  Sidebar _nativeSidebar(MagnusTheme t) => Sidebar(
        minWidth: 224,
        top: ShellBrand(theme: t, extended: true),
        bottom: Padding(
          padding: const EdgeInsets.all(10),
          child: _AppleItem(
            dest: magnusDestinations[_settings],
            selected: _index == _settings,
            theme: t,
            onTap: () => _select(_settings),
          ),
        ),
        builder: (context, scrollController) => SidebarItems(
          // Con Ajustes activo, la lista no marca nada.
          currentIndex: _index.clamp(0, _settings - 1),
          scrollController: scrollController,
          selectedColor: _index == _settings ? const Color(0x00000000) : t.accentSoft,
          unselectedColor: const Color(0x00000000),
          itemSize: SidebarItemSize.large,
          onChanged: _select,
          items: [
            for (final d in magnusDestinations.take(_settings))
              SidebarItem(
                leading: MacosIcon(d.iconFor(DesignSystem.apple)),
                label: Text(d.label),
              ),
          ],
        ),
      );
}

/// Réplica de la barra lateral de macOS para Windows y Linux: fondo del
/// material «sidebar», título de sección gris y selección redondeada.
class _ReplicaSidebar extends StatelessWidget {
  const _ReplicaSidebar({required this.theme, required this.index, required this.onSelect});
  final MagnusTheme theme;
  final int index;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    final settings = magnusDestinations.length - 1;
    return Container(
      width: 232,
      decoration: BoxDecoration(
        color: t.isDark ? const Color(0xFF252528) : const Color(0xFFE8E8EB),
        border: Border(right: BorderSide(color: t.stroke)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ShellBrand(theme: t, extended: true),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 6),
            child: Text('Navegación',
                style: TextStyle(
                    color: t.textFaint, fontSize: 11, fontWeight: FontWeight.w700)),
          ),
          for (var i = 0; i < settings; i++)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 1),
              child: _AppleItem(
                dest: magnusDestinations[i],
                selected: index == i,
                theme: t,
                onTap: () => onSelect(i),
              ),
            ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
            child: _AppleItem(
              dest: magnusDestinations[settings],
              selected: index == settings,
              theme: t,
              onTap: () => onSelect(settings),
            ),
          ),
        ],
      ),
    );
  }
}

/// Elemento de barra lateral al estilo macOS: icono con el acento, etiqueta
/// de 13 pt y selección redondeada.
class _AppleItem extends StatefulWidget {
  const _AppleItem({
    required this.dest,
    required this.selected,
    required this.theme,
    required this.onTap,
  });
  final NavDest dest;
  final bool selected;
  final MagnusTheme theme;
  final VoidCallback onTap;

  @override
  State<_AppleItem> createState() => _AppleItemState();
}

class _AppleItemState extends State<_AppleItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final t = widget.theme;
    final fill = widget.selected
        ? t.accentSoft
        : (_hover ? t.stateLayer() : const Color(0x00000000));
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          height: 32,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(color: fill, borderRadius: BorderRadius.circular(t.radiusSm)),
          child: Row(
            children: [
              Icon(widget.dest.iconFor(DesignSystem.apple), size: 17, color: t.accent),
              const SizedBox(width: 10),
              Text(widget.dest.label,
                  style: TextStyle(
                      color: t.text,
                      fontSize: 13,
                      fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w400)),
            ],
          ),
        ),
      ),
    );
  }
}
