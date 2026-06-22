import 'dart:ui' as ui;

import 'package:flutter/widgets.dart';

import '../../core/theme/magnus_theme.dart';

/// Tarjeta base de Magnus. En temas con `glass` aplica desenfoque (frosted
/// glass) sobre un relleno translúcido; si no, usa una superficie opaca con
/// sombra suave. Es el contenedor que da identidad por tema. Cuando es
/// interactiva (`onTap`), resalta sutilmente al pasar el cursor (escritorio).
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

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final interactive = widget.onTap != null;
    final radius = BorderRadius.circular(t.radiusLg);
    final fill = widget.strong ? t.surfaceStrong : t.surface;
    final highlight = interactive && _hover;
    final borderColor = widget.selected || widget.accentBorder || highlight
        ? t.accent
        : (widget.strong ? t.strokeStrong : t.stroke);

    Widget content = AnimatedContainer(
      duration: const Duration(milliseconds: 120),
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

    if (t.glass) {
      content = DecoratedBox(
        decoration: BoxDecoration(borderRadius: radius, boxShadow: t.shadow),
        child: ClipRRect(
          borderRadius: radius,
          child: BackdropFilter(
            filter:
                ui.ImageFilter.blur(sigmaX: t.blurSigma, sigmaY: t.blurSigma),
            child: content,
          ),
        ),
      );
    }

    if (interactive) {
      content = MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: _Pressable(onTap: widget.onTap!, child: content),
      );
    }
    return content;
  }
}

/// Encabezado de página consistente: título grande, subtítulo y acciones.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.icon,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: t.accentSoft,
                borderRadius: BorderRadius.circular(t.radius),
              ),
              alignment: Alignment.center,
              child: Icon(icon, size: 20, color: t.accent),
            ),
            const SizedBox(width: 14),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: t.display),
                if (subtitle != null) ...[
                  const SizedBox(height: 3),
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

/// Botón principal (acento) o secundario, sin depender de Material.
class MagnusButton extends StatelessWidget {
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
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final enabled = onTap != null;
    final bg = primary ? t.accent : t.surfaceAlt;
    final fg = primary ? t.onAccent : t.text;
    return _Pressable(
      onTap: onTap,
      child: Opacity(
        opacity: enabled ? 1 : 0.45,
        child: Container(
          padding: EdgeInsets.symmetric(
              horizontal: dense ? 12 : 16, vertical: dense ? 7 : 10),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(t.radius),
            border: primary ? null : Border.all(color: t.stroke),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: dense ? 15 : 17, color: fg),
                const SizedBox(width: 7),
              ],
              Text(label,
                  style: TextStyle(
                      color: fg,
                      fontSize: dense ? 12.5 : 13.5,
                      fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Etiqueta compacta (chip) para estados/metadatos.
class Pill extends StatelessWidget {
  const Pill(this.label, {super.key, this.color, this.icon});
  final String label;
  final Color? color;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final c = color ?? t.textMuted;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: c),
            const SizedBox(width: 4),
          ],
          Text(label,
              style: TextStyle(
                  color: c, fontSize: 11.5, fontWeight: FontWeight.w600)),
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

/// Barra de progreso/uso temada.
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
        child: FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: f == 0 ? 0.001 : f,
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [c.withValues(alpha: 0.7), c],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Estado vacío / placeholder elegante para secciones pendientes de backend.
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
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: t.accentSoft,
                borderRadius: BorderRadius.circular(t.radiusLg),
              ),
              alignment: Alignment.center,
              child: Icon(icon, size: 26, color: t.accent),
            ),
            const SizedBox(height: 16),
            Text(title, style: t.h2, textAlign: TextAlign.center),
            if (message != null) ...[
              const SizedBox(height: 6),
              SizedBox(
                width: 340,
                child: Text(message!,
                    style: t.small, textAlign: TextAlign.center),
              ),
            ],
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}

/// Envoltura de página: aplica el fondo del tema y un padding consistente,
/// con scroll vertical. Centra el contenido a un ancho máximo legible.
class PageScaffold extends StatelessWidget {
  const PageScaffold({
    super.key,
    required this.child,
    this.scroll = true,
    this.maxWidth = 1080,
    this.padding = const EdgeInsets.fromLTRB(28, 26, 28, 28),
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
