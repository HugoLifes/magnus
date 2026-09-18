import 'package:fluent_ui/fluent_ui.dart' hide FluentIcons;
import 'package:fluentui_system_icons/fluentui_system_icons.dart';
import 'package:flutter/material.dart' show Material;
import 'package:sidebarx/sidebarx.dart';

import '../../app.dart';
import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';
import '../widgets/shell_chrome.dart';

/// Shell de diseño Windows: FluentApp + barra lateral colapsable (sidebarx)
/// sobre un fondo Acrylic translúcido (glassmorphism). Oscuro por defecto.
class WindowsShell extends StatefulWidget {
  const WindowsShell({
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
  State<WindowsShell> createState() => _WindowsShellState();
}

class _WindowsShellState extends State<WindowsShell> {
  late final _controller =
      SidebarXController(selectedIndex: widget.initialPage, extended: true);

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
    final t = MagnusTheme.forDesign(DesignSystem.windows, widget.appearance.brightness,
        font: widget.font, accent: widget.accent);

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
      home: ShellBackdrop(
        theme: t,
        opaque: false,
        child: Material(
          color: const Color(0x00000000),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Sidebar(controller: _controller, theme: t),
              Expanded(
                child: themedPage(DesignSystem.windows, widget.appearance,
                    widget.font, widget.accent, _controller.selectedIndex),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Panel de navegación al estilo `NavigationView` de WinUI 3: relleno suave al
/// pasar el cursor, píldora de acento a la izquierda del elemento activo y
/// Ajustes separado abajo, como en las apps de Windows 11.
class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.controller, required this.theme});
  final SidebarXController controller;
  final MagnusTheme theme;

  static const _settings = 7; // índice de Ajustes en magnusDestinations

  SidebarXItem _item(NavDest d) => SidebarXItem(
        label: d.label,
        iconBuilder: (selected, hovered) => _NavIcon(
          icon: d.iconFor(DesignSystem.windows),
          selected: selected,
          hovered: hovered,
          theme: theme,
        ),
      );

  SidebarXTheme _theme({required bool extended}) {
    final t = theme;
    final pad = EdgeInsets.symmetric(horizontal: extended ? 4 : 10, vertical: 9);
    final margin = EdgeInsets.symmetric(horizontal: extended ? 8 : 6, vertical: 1.5);
    return SidebarXTheme(
      width: extended ? 232 : 64,
      decoration: BoxDecoration(
        color: t.isDark ? const Color(0x0AFFFFFF) : const Color(0x80FFFFFF),
        border: Border(right: BorderSide(color: t.stroke)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      itemPadding: pad,
      selectedItemPadding: pad,
      itemMargin: margin,
      selectedItemMargin: margin,
      itemTextPadding: const EdgeInsets.only(left: 12),
      selectedItemTextPadding: const EdgeInsets.only(left: 12),
      textStyle: TextStyle(color: t.textMuted, fontSize: 13.5, fontWeight: FontWeight.w500),
      hoverTextStyle: TextStyle(color: t.text, fontSize: 13.5, fontWeight: FontWeight.w500),
      selectedTextStyle:
          TextStyle(color: t.text, fontSize: 13.5, fontWeight: FontWeight.w600),
      iconTheme: IconThemeData(color: t.textMuted, size: 20),
      selectedIconTheme: IconThemeData(color: t.accent, size: 20),
      hoverColor: t.stateLayer(),
      itemDecoration: BoxDecoration(borderRadius: BorderRadius.circular(t.radiusSm)),
      selectedItemDecoration: BoxDecoration(
        color: t.stateLayer(pressed: true),
        borderRadius: BorderRadius.circular(t.radiusSm),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return SidebarX(
      controller: controller,
      showToggleButton: true,
      headerBuilder: (context, extended) => ShellBrand(theme: t, extended: extended),
      footerDivider: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        child: Container(height: 1, color: t.stroke),
      ),
      footerBuilder: (context, extended) => _FooterItem(
        dest: magnusDestinations[_settings],
        extended: extended,
        selected: controller.selectedIndex == _settings,
        theme: t,
        onTap: () => controller.selectIndex(_settings),
      ),
      toggleButtonBuilder: (context, extended) => _CollapseButton(
        extended: extended,
        theme: t,
        onTap: () => controller.setExtended(!extended),
      ),
      extendedTheme: _theme(extended: true),
      theme: _theme(extended: false),
      // Ajustes es el último destino: fuera de la lista, en el pie.
      items: [for (final d in magnusDestinations.take(_settings)) _item(d)],
    );
  }
}

/// Elemento del pie (Ajustes) con el mismo aspecto que los de la lista.
class _FooterItem extends StatefulWidget {
  const _FooterItem({
    required this.dest,
    required this.extended,
    required this.selected,
    required this.theme,
    required this.onTap,
  });
  final NavDest dest;
  final bool extended;
  final bool selected;
  final MagnusTheme theme;
  final VoidCallback onTap;

  @override
  State<_FooterItem> createState() => _FooterItemState();
}

class _FooterItemState extends State<_FooterItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final t = widget.theme;
    final fill = widget.selected
        ? t.stateLayer(pressed: true)
        : (_hover ? t.stateLayer() : const Color(0x00000000));
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          margin: EdgeInsets.symmetric(horizontal: widget.extended ? 8 : 6, vertical: 1.5),
          padding: EdgeInsets.symmetric(horizontal: widget.extended ? 4 : 10, vertical: 9),
          decoration: BoxDecoration(color: fill, borderRadius: BorderRadius.circular(t.radiusSm)),
          child: Row(
            mainAxisAlignment:
                widget.extended ? MainAxisAlignment.start : MainAxisAlignment.center,
            children: [
              _NavIcon(
                icon: widget.dest.iconFor(DesignSystem.windows),
                selected: widget.selected,
                hovered: _hover,
                theme: t,
              ),
              if (widget.extended) ...[
                const SizedBox(width: 12),
                Text(widget.dest.label,
                    style: TextStyle(
                        color: widget.selected || _hover ? t.text : t.textMuted,
                        fontSize: 13.5,
                        fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w500)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Icono del panel con la píldora de selección de Fluent a su izquierda.
class _NavIcon extends StatelessWidget {
  const _NavIcon({
    required this.icon,
    required this.selected,
    required this.hovered,
    required this.theme,
  });
  final IconData icon;
  final bool selected;
  final bool hovered;
  final MagnusTheme theme;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeOut,
          width: 3,
          height: selected ? 16 : 0,
          decoration: BoxDecoration(
            color: t.accent,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 9),
        Icon(icon,
            size: 20,
            color: selected ? t.accent : (hovered ? t.text : t.textMuted)),
      ],
    );
  }
}

/// Botón para plegar el panel, abajo como en el explorador de Windows 11.
class _CollapseButton extends StatelessWidget {
  const _CollapseButton({required this.extended, required this.theme, required this.onTap});
  final bool extended;
  final MagnusTheme theme;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return Padding(
      padding: EdgeInsets.fromLTRB(extended ? 14 : 0, 2, 14, 4),
      child: Align(
        alignment: extended ? Alignment.centerLeft : Alignment.center,
        child: HoverButton(
          onPressed: onTap,
          builder: (context, states) => Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: states.isHovered ? t.stateLayer() : const Color(0x00000000),
              borderRadius: BorderRadius.circular(t.radiusSm),
            ),
            child: Icon(
              extended
                  ? FluentIcons.panel_left_contract_24_regular
                  : FluentIcons.panel_left_expand_24_regular,
              size: 18,
              color: t.textMuted,
            ),
          ),
        ),
      ),
    );
  }
}
