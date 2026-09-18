import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/widgets.dart';

import '../../core/theme/design_system.dart';
import '../../core/theme/magnus_theme.dart';

/// Tarjeta base de Magnus.
///
/// Tres capas, en este orden: relleno de la piel (cristal en Windows/Apple,
/// tonal en Material), el **foco de luz que sigue al cursor** — el mismo gesto
/// que la web de Magnus — y el borde, que se tiñe de acento al pasar por encima
/// o cuando la tarjeta está seleccionada.
class GlassCard extends StatefulWidget {
  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.strong = false,
    this.onTap,
    this.selected = false,
    this.accentBorder = false,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final bool strong; // superficie más sólida (destacar)
  final VoidCallback? onTap;
  final bool selected;
  final bool accentBorder;

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard> {
  bool _hover = false;
  Offset? _cursor;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final interactive = widget.onTap != null;
    final radius = BorderRadius.circular(t.radiusLg);
    final fill = widget.strong ? t.surfaceStrong : t.surface;
    final highlight = _hover && (interactive || t.spotlight > 0);
    final borderColor = widget.selected || widget.accentBorder || (highlight && interactive)
        ? t.accent
        : (widget.strong ? t.strokeStrong : t.stroke);

    Widget content = AnimatedContainer(
      duration: const Duration(milliseconds: 140),
      curve: Curves.easeOut,
      padding: widget.padding,
      decoration: BoxDecoration(
        color: fill,
        borderRadius: radius,
        border: Border.all(
            color: borderColor,
            width: widget.selected || widget.accentBorder || highlight ? 1.4 : 1),
        boxShadow: t.glass ? null : t.shadow,
      ),
      child: widget.child,
    );

    // Foco de luz bajo el contenido: se ve el brillo, no una mancha encima.
    // Los Stack usan passthrough: si la página estira la tarjeta a lo ancho,
    // la tarjeta debe llenar ese ancho y no encogerse a su contenido.
    if (t.spotlight > 0 && _cursor != null && _hover) {
      content = Stack(
        fit: StackFit.passthrough,
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: ClipRRect(
                borderRadius: radius,
                child: CustomPaint(
                  painter: _SpotlightPainter(
                    center: _cursor!,
                    color: t.accent.withValues(alpha: 0.16 * t.spotlight),
                  ),
                ),
              ),
            ),
          ),
          content,
        ],
      );
    }

    if (t.glass) {
      // Brillo de borde superior: la luz que atrapa el cristal esmerilado.
      final highlightLine = Color(t.isDark ? 0x26FFFFFF : 0x80FFFFFF);
      content = DecoratedBox(
        decoration: BoxDecoration(borderRadius: radius, boxShadow: t.shadow),
        child: ClipRRect(
          borderRadius: radius,
          child: BackdropFilter(
            filter: ui.ImageFilter.blur(sigmaX: t.blurSigma, sigmaY: t.blurSigma),
            child: Stack(
              fit: StackFit.passthrough,
              children: [
                content,
                Positioned(
                  top: 0,
                  left: t.radiusLg,
                  right: t.radiusLg,
                  child: IgnorePointer(
                    child: Container(height: 1, color: highlightLine),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    content = MouseRegion(
      cursor: interactive ? SystemMouseCursors.click : MouseCursor.defer,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() {
        _hover = false;
        _cursor = null;
      }),
      onHover: t.spotlight > 0 ? (e) => setState(() => _cursor = e.localPosition) : null,
      child: interactive ? _Pressable(onTap: widget.onTap, child: content) : content,
    );
    return content;
  }
}

class _SpotlightPainter extends CustomPainter {
  const _SpotlightPainter({required this.center, required this.color});
  final Offset center;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final radius = size.shortestSide * 1.4;
    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..shader = ui.Gradient.radial(center, radius, [color, color.withValues(alpha: 0)]),
    );
  }

  @override
  bool shouldRepaint(_SpotlightPainter old) => old.center != center || old.color != color;
}

/// Encabezado de página, el mismo de la web: icono pequeño y etiqueta en
/// mayúsculas con el acento, título grande en la tipografía de marca y, a la
/// derecha, las acciones de la página.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.icon,
    this.eyebrow,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;
  final IconData? icon;

  /// Palabra corta sobre el título (va en mayúsculas y con el color de acento).
  final String? eyebrow;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: 22 * t.density),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (eyebrow != null || icon != null) ...[
                  _EyebrowRow(icon: icon, text: eyebrow),
                  const SizedBox(height: 6),
                ],
                Text(title, style: t.display),
                if (subtitle != null) ...[
                  const SizedBox(height: 5),
                  Text(subtitle!, style: t.body.copyWith(color: t.textMuted)),
                ],
              ],
            ),
          ),
          if (trailing != null) ...[const SizedBox(width: 16), trailing!],
        ],
      ),
    );
  }
}

class _EyebrowRow extends StatelessWidget {
  const _EyebrowRow({this.icon, this.text});
  final IconData? icon;
  final String? text;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) Icon(icon, size: 14, color: t.accent),
        if (icon != null && text != null) const SizedBox(width: 7),
        if (text != null) Text(text!.toUpperCase(), style: t.eyebrow),
      ],
    );
  }
}

/// Botón principal (acento con el degradado de marca) o secundario.
class MagnusButton extends StatefulWidget {
  const MagnusButton({
    super.key,
    required this.label,
    this.onTap,
    this.icon,
    this.primary = true,
    this.dense = false,
  });

  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final bool primary;
  final bool dense;

  @override
  State<MagnusButton> createState() => _MagnusButtonState();
}

class _MagnusButtonState extends State<MagnusButton> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final enabled = widget.onTap != null;
    final fg = widget.primary ? t.onAccent : t.text;
    final radius = BorderRadius.circular(
        t.design == DesignSystem.material ? 999 : t.radius);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: _Pressable(
        onTap: widget.onTap,
        child: Opacity(
          opacity: enabled ? 1 : 0.45,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 140),
            padding: EdgeInsets.symmetric(
                horizontal: widget.dense ? 13 : 17, vertical: widget.dense ? 8 : 11),
            decoration: BoxDecoration(
              gradient: widget.primary ? t.brandGradient : null,
              color: widget.primary
                  ? null
                  : (_hover && enabled ? t.surfaceStrong : t.surfaceAlt),
              borderRadius: radius,
              border: widget.primary ? null : Border.all(color: t.stroke),
              boxShadow: widget.primary && enabled
                  ? [
                      BoxShadow(
                        color: t.accent.withValues(alpha: _hover ? 0.45 : 0.28),
                        blurRadius: _hover ? 22 : 14,
                        offset: const Offset(0, 6),
                      ),
                    ]
                  : null,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: widget.dense ? 15 : 17, color: fg),
                  const SizedBox(width: 7),
                ],
                Text(widget.label,
                    style: TextStyle(
                        color: fg,
                        fontSize: widget.dense ? 12.5 : 13.5,
                        fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Etiqueta compacta para estados y metadatos.
class Pill extends StatelessWidget {
  const Pill(this.label, {super.key, this.color, this.icon, this.solid = false});
  final String label;
  final Color? color;
  final IconData? icon;

  /// Rellena con el color (para el estado que manda en la pantalla).
  final bool solid;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final c = color ?? t.textMuted;
    final fg = solid ? (t.isDark ? const Color(0xFF12101F) : const Color(0xFFFFFFFF)) : c;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: c.withValues(alpha: solid ? 0.92 : 0.13),
        borderRadius: BorderRadius.circular(999),
        border: solid ? null : Border.all(color: c.withValues(alpha: 0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 5),
          ],
          Text(label,
              style: TextStyle(color: fg, fontSize: 11.5, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// Punto de estado (verde/ámbar/rojo) con leve glow.
class StatusDot extends StatelessWidget {
  const StatusDot(this.color, {super.key, this.size = 9});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        boxShadow: [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 6)],
      ),
    );
  }
}

/// Cifra grande con su etiqueta: la unidad de información de Magnus.
/// El número va en monoespaciada tabular para que no baile al actualizarse.
class StatTile extends StatelessWidget {
  const StatTile({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.sub,
    this.tone,
    this.width,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? sub;
  final Color? tone;

  /// Ancho fijo; nulo cuando lo decide el contenedor (p. ej. [TileGrid]).
  final double? width;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final c = tone ?? t.accent;
    final card = GlassCard(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: c.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(t.radiusSm),
                  ),
                  alignment: Alignment.center,
                  child: Icon(icon, size: 16, color: c),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: t.small.copyWith(fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: RegExp(r'\d').hasMatch(value)
                    ? t.numeral
                    : t.h1.copyWith(fontSize: 24, height: 1.1)),
            if (sub != null) ...[
              const SizedBox(height: 4),
              Text(sub!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: t.small.copyWith(fontSize: 11.5, color: t.textFaint)),
            ],
          ],
        ),
      );
    return width == null ? card : SizedBox(width: width, child: card);
  }
}

/// Título de sección dentro de una página: etiqueta corta + título.
class SubHeading extends StatelessWidget {
  const SubHeading(this.title,
      {super.key, this.eyebrow, this.icon, this.subtitle, this.trailing});
  final String title;
  final String? eyebrow;
  final IconData? icon;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: EdgeInsets.only(top: 8 * t.density, bottom: 14 * t.density),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (eyebrow != null || icon != null) ...[
                  _EyebrowRow(icon: icon, text: eyebrow),
                  const SizedBox(height: 5),
                ],
                Text(title, style: t.h1),
                if (subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(subtitle!, style: t.small),
                ],
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

/// Rejilla que reparte el ancho entre columnas iguales: hasta 4 en escritorio
/// ancho, 2 en ventanas medianas y 1 en estrechas, sin tarjetas huérfanas.
class TileGrid extends StatelessWidget {
  const TileGrid({super.key, required this.children, this.minTileWidth = 220, this.spacing = 14});
  final List<Widget> children;
  final double minTileWidth;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final n = children.length;
      final fit = ((c.maxWidth + spacing) / (minTileWidth + spacing)).floor().clamp(1, 4);
      // Entre las columnas que caben, la que deja menos huecos en la última fila
      // (4 tarjetas: 2×2 antes que 3+1). Nunca menos de la mitad de las que caben
      // ni una sola columna si caben dos: 2+1 se ve mejor que tres franjas.
      var cols = fit.clamp(1, n);
      final minCols = fit >= 2 ? math.max(2, (fit / 2).ceil()) : 1;
      for (var k = cols; k >= minCols; k--) {
        if ((k - n % k) % k < (cols - n % cols) % cols) cols = k;
      }
      final w = (c.maxWidth - spacing * (cols - 1)) / cols;
      return Wrap(
        spacing: spacing,
        runSpacing: spacing,
        children: [for (final child in children) SizedBox(width: w.floorToDouble(), child: child)],
      );
    });
  }
}

/// Barra de progreso/uso temada, con el degradado de marca.
class UsageBar extends StatelessWidget {
  const UsageBar({super.key, required this.fraction, this.color, this.height = 8});
  final double fraction;
  final Color? color;
  final double height;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final f = fraction.clamp(0.0, 1.0);
    final c = color ?? t.accent;
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: Container(
        height: height,
        color: t.surfaceAlt,
        // A 0 % no se pinta relleno: el brillo de una barra vacía parece una raya.
        child: f <= 0
            ? null
            : FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: f,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 260),
                  curve: Curves.easeOut,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [c.withValues(alpha: 0.65), c]),
                    boxShadow: [BoxShadow(color: c.withValues(alpha: 0.35), blurRadius: 8)],
                  ),
                ),
              ),
      ),
    );
  }
}

/// Estado vacío: qué falta y qué hacer.
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.action,
  });
  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [t.accent.withValues(alpha: 0.22), t.accent.withValues(alpha: 0.06)],
                ),
                borderRadius: BorderRadius.circular(t.radiusLg),
                border: Border.all(color: t.accent.withValues(alpha: 0.28)),
              ),
              alignment: Alignment.center,
              child: Icon(icon, size: 26, color: t.accent),
            ),
            const SizedBox(height: 18),
            Text(title, style: t.h1, textAlign: TextAlign.center),
            if (message != null) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: 380,
                child: Text(message!, style: t.small, textAlign: TextAlign.center),
              ),
            ],
            if (action != null) ...[const SizedBox(height: 20), action!],
          ],
        ),
      ),
    );
  }
}

/// Envoltura de página: fondo del tema, ancho legible y scroll vertical.
class PageScaffold extends StatelessWidget {
  const PageScaffold({
    super.key,
    required this.child,
    this.scroll = true,
    this.maxWidth = 1120,
    this.padding = const EdgeInsets.fromLTRB(30, 28, 30, 30),
  });
  final Widget child;
  final bool scroll;
  final double maxWidth;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    Widget inner = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Padding(padding: padding, child: child),
      ),
    );
    if (scroll) inner = SingleChildScrollView(child: inner);
    return Container(color: t.glass ? null : t.bg, child: inner);
  }
}

/// Detector de pulsación con leve animación de escala (feedback táctil).
class _Pressable extends StatefulWidget {
  const _Pressable({required this.child, this.onTap});
  final Widget child;
  final VoidCallback? onTap;
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    if (widget.onTap == null) return widget.child;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTapDown: (_) => setState(() => _down = true),
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) => setState(() => _down = false),
        onTap: widget.onTap,
        child: AnimatedScale(
          scale: _down ? 0.98 : 1,
          duration: const Duration(milliseconds: 90),
          child: widget.child,
        ),
      ),
    );
  }
}
