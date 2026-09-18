import 'dart:math' as math;

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import '../../core/theme/icons.dart';

import '../../core/theme/brand.dart';
import '../../core/theme/magnus_theme.dart';

/// Kit visual propio de Magnus: aurora, botones con brillo, tarjetas con foco,
/// distintivo de ajuste, chip de ubicación y anillo de créditos.
///
/// Todo respeta «reducir movimiento» del sistema: sin animaciones, los
/// componentes quedan en su estado final y siguen leyéndose igual.

bool _reduceMotion(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;

// ---------------------------------------------------------------------------
// Aurora
// ---------------------------------------------------------------------------

/// Fondo con tres luces difusas que derivan despacio, como una aurora.
/// Pensado para cabeceras y secciones héroe, no para todo el fondo: la aurora
/// llama la atención y se gasta si está en todas partes.
class AuroraBackdrop extends StatefulWidget {
  const AuroraBackdrop({super.key, required this.child, this.intensity = 1, this.radius});
  final Widget child;
  final double intensity;
  final BorderRadius? radius;

  @override
  State<AuroraBackdrop> createState() => _AuroraBackdropState();
}

class _AuroraBackdropState extends State<AuroraBackdrop> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(seconds: 24));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_reduceMotion(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final strength = (t.isDark ? 0.38 : 0.22) * widget.intensity;
    return ClipRRect(
      borderRadius: widget.radius ?? BorderRadius.circular(t.radiusLg),
      child: Stack(
        children: [
          Positioned.fill(
            child: RepaintBoundary(
              child: CustomPaint(
                painter: _AuroraPainter(_c, t.accent, strength),
              ),
            ),
          ),
          widget.child,
        ],
      ),
    );
  }
}

class _AuroraPainter extends CustomPainter {
  _AuroraPainter(this.progress, this.accent, this.strength) : super(repaint: progress);
  final Animation<double> progress;
  final Color accent;
  final double strength;

  @override
  void paint(Canvas canvas, Size size) {
    final a = progress.value * 2 * math.pi;
    final blobs = <(Offset, double, Color)>[
      (Offset(0.22 + 0.10 * math.sin(a), 0.30 + 0.12 * math.cos(a * 0.8)), 0.70, accent),
      (Offset(0.72 + 0.12 * math.cos(a * 0.7), 0.25 + 0.10 * math.sin(a * 1.3)), 0.60,
          Brand.sky),
      (Offset(0.55 + 0.14 * math.sin(a * 0.5 + 1), 0.85 + 0.08 * math.cos(a)), 0.65,
          Brand.periwinkle),
    ];
    for (final (center, radius, color) in blobs) {
      final c = Offset(center.dx * size.width, center.dy * size.height);
      final r = radius * math.max(size.width, size.height);
      final paint = Paint()
        ..shader = RadialGradient(colors: [
          color.withValues(alpha: strength),
          color.withValues(alpha: 0),
        ]).createShader(Rect.fromCircle(center: c, radius: r));
      canvas.drawCircle(c, r, paint);
    }
  }

  @override
  bool shouldRepaint(_AuroraPainter old) => old.accent != accent || old.strength != strength;
}

// ---------------------------------------------------------------------------
// Botón con brillo
// ---------------------------------------------------------------------------

enum GlowVariant { primary, secondary, savings }

/// Botón de acción de Magnus. El primario lleva el degradado de marca, un halo
/// que crece al pasar el cursor y un destello que lo cruza una vez. Accesible
/// por teclado (Enter/Espacio) y con anillo de foco visible.
class GlowButton extends StatefulWidget {
  const GlowButton({
    super.key,
    required this.label,
    this.onTap,
    this.icon,
    this.variant = GlowVariant.primary,
    this.busy = false,
    this.dense = false,
    this.expand = false,
  });

  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final GlowVariant variant;
  final bool busy;
  final bool dense;
  final bool expand;

  @override
  State<GlowButton> createState() => _GlowButtonState();
}

class _GlowButtonState extends State<GlowButton> with SingleTickerProviderStateMixin {
  bool _hover = false;
  bool _down = false;
  bool _focus = false;
  late final AnimationController _shine =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900));

  bool get _enabled => widget.onTap != null && !widget.busy;

  @override
  void dispose() {
    _shine.dispose();
    super.dispose();
  }

  void _setHover(bool value) {
    setState(() => _hover = value);
    if (value && _enabled && !_reduceMotion(context)) _shine.forward(from: 0);
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final primary = widget.variant == GlowVariant.primary;
    final savings = widget.variant == GlowVariant.savings;
    final glowColor = savings ? Brand.amber : t.accent;
    final radius = BorderRadius.circular(t.radius + 2);

    final Gradient? fill = switch (widget.variant) {
      GlowVariant.primary => LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [t.accent, Color.lerp(t.accent, Brand.sky, 0.55)!],
        ),
      GlowVariant.savings => Brand.savings,
      GlowVariant.secondary => null,
    };
    final fg = switch (widget.variant) {
      GlowVariant.primary => const Color(0xFFFFFFFF),
      GlowVariant.savings => Brand.night,
      GlowVariant.secondary => t.text,
    };

    final content = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.busy)
          SizedBox(
            width: 14,
            height: 14,
            child: _Spinner(color: fg),
          )
        else if (widget.icon != null)
          Icon(widget.icon, size: widget.dense ? 15 : 17, color: fg),
        if (widget.busy || widget.icon != null) const SizedBox(width: 8),
        Flexible(
          child: Text(widget.label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: fg,
                fontSize: widget.dense ? 12.5 : 13.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.1,
              )),
        ),
      ],
    );

    final lifted = _enabled && (_hover || _focus);
    final button = AnimatedContainer(
      duration: const Duration(milliseconds: 160),
      curve: Curves.easeOut,
      padding: EdgeInsets.symmetric(horizontal: widget.dense ? 14 : 18, vertical: widget.dense ? 8 : 11),
      decoration: BoxDecoration(
        gradient: fill,
        color: fill == null ? (lifted ? t.surfaceStrong : t.surfaceAlt) : null,
        borderRadius: radius,
        border: fill == null
            ? Border.all(color: lifted ? t.accent.withValues(alpha: 0.6) : t.stroke)
            : Border.all(color: const Color(0x33FFFFFF)),
        boxShadow: [
          if (fill != null)
            BoxShadow(
              color: glowColor.withValues(alpha: lifted ? 0.55 : 0.28),
              blurRadius: lifted ? 26 : 14,
              spreadRadius: lifted ? 1 : 0,
              offset: const Offset(0, 6),
            ),
          if (_focus) BoxShadow(color: t.accent.withValues(alpha: 0.9), spreadRadius: 2),
        ],
      ),
      child: content,
    );

    final shined = primary || savings
        ? ClipRRect(
            borderRadius: radius,
            child: Stack(children: [
              button,
              Positioned.fill(
                child: IgnorePointer(
                  child: AnimatedBuilder(
                    animation: _shine,
                    builder: (context, _) => _shine.isAnimating
                        ? FractionalTranslation(
                            translation: Offset(-1.2 + 2.4 * _shine.value, 0),
                            child: const DecoratedBox(
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [Color(0x00FFFFFF), Color(0x55FFFFFF), Color(0x00FFFFFF)],
                                  stops: [0.3, 0.5, 0.7],
                                ),
                              ),
                            ),
                          )
                        : const SizedBox.shrink(),
                  ),
                ),
              ),
            ]),
          )
        : button;

    return FocusableActionDetector(
      enabled: _enabled,
      mouseCursor: _enabled ? SystemMouseCursors.click : SystemMouseCursors.forbidden,
      onShowHoverHighlight: _setHover,
      onShowFocusHighlight: (v) => setState(() => _focus = v),
      shortcuts: const {
        SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
      },
      actions: {
        ActivateIntent: CallbackAction<ActivateIntent>(onInvoke: (_) {
          widget.onTap?.call();
          return null;
        }),
      },
      child: GestureDetector(
        onTapDown: _enabled ? (_) => setState(() => _down = true) : null,
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) => setState(() => _down = false),
        onTap: _enabled ? widget.onTap : null,
        child: AnimatedScale(
          scale: _down ? 0.97 : (lifted ? 1.02 : 1),
          duration: const Duration(milliseconds: 120),
          child: AnimatedOpacity(
            opacity: widget.onTap == null ? 0.45 : 1,
            duration: const Duration(milliseconds: 120),
            child: shined,
          ),
        ),
      ),
    );
  }
}

class _Spinner extends StatefulWidget {
  const _Spinner({required this.color});
  final Color color;
  @override
  State<_Spinner> createState() => _SpinnerState();
}

class _SpinnerState extends State<_Spinner> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 800))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RotationTransition(
        turns: _c,
        child: CustomPaint(painter: _ArcPainter(widget.color)),
      );
}

class _ArcPainter extends CustomPainter {
  _ArcPainter(this.color);
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(Offset.zero & size, 0, math.pi * 1.4, false, paint);
  }

  @override
  bool shouldRepaint(_ArcPainter old) => old.color != color;
}

// ---------------------------------------------------------------------------
// Tarjeta con foco
// ---------------------------------------------------------------------------

/// Tarjeta con un foco de luz que sigue al cursor y un borde con degradado.
/// `featured` gira el degradado del borde despacio: marca LA opción
/// recomendada de un grupo (un solo paquete destacado, no varios).
class SpotlightCard extends StatefulWidget {
  const SpotlightCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.onTap,
    this.featured = false,
    this.glow,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final bool featured;
  final Color? glow;

  @override
  State<SpotlightCard> createState() => _SpotlightCardState();
}

class _SpotlightCardState extends State<SpotlightCard> with SingleTickerProviderStateMixin {
  Offset? _pointer;
  late final AnimationController _spin =
      AnimationController(vsync: this, duration: const Duration(seconds: 6));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncSpin();
  }

  @override
  void didUpdateWidget(SpotlightCard old) {
    super.didUpdateWidget(old);
    _syncSpin();
  }

  void _syncSpin() {
    if (widget.featured && !_reduceMotion(context)) {
      if (!_spin.isAnimating) _spin.repeat();
    } else {
      _spin.stop();
    }
  }

  @override
  void dispose() {
    _spin.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final glow = widget.glow ?? t.accent;
    final radius = t.radiusLg;

    Widget card = CustomPaint(
      foregroundPainter: _BorderPainter(
        animation: _spin,
        radius: radius,
        featured: widget.featured,
        base: t.stroke,
        glow: glow,
        hover: _pointer != null,
      ),
      child: Container(
        decoration: BoxDecoration(
          color: widget.featured ? t.surfaceStrong : t.surface,
          borderRadius: BorderRadius.circular(radius),
          boxShadow: [
            if (widget.featured)
              BoxShadow(color: glow.withValues(alpha: 0.22), blurRadius: 34, offset: const Offset(0, 14)),
            ...t.shadow,
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: Stack(
            children: [
              if (_pointer != null)
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(painter: _SpotPainter(_pointer!, glow, t.isDark)),
                  ),
                ),
              Padding(padding: widget.padding, child: widget.child),
            ],
          ),
        ),
      ),
    );

    card = MouseRegion(
      cursor: widget.onTap != null ? SystemMouseCursors.click : MouseCursor.defer,
      onHover: (e) => setState(() => _pointer = e.localPosition),
      onExit: (_) => setState(() => _pointer = null),
      child: card,
    );
    if (widget.onTap != null) {
      card = GestureDetector(onTap: widget.onTap, child: card);
    }
    return card;
  }
}

class _SpotPainter extends CustomPainter {
  _SpotPainter(this.center, this.color, this.dark);
  final Offset center;
  final Color color;
  final bool dark;

  @override
  void paint(Canvas canvas, Size size) {
    const r = 220.0;
    canvas.drawCircle(
      center,
      r,
      Paint()
        ..shader = RadialGradient(colors: [
          color.withValues(alpha: dark ? 0.16 : 0.10),
          color.withValues(alpha: 0),
        ]).createShader(Rect.fromCircle(center: center, radius: r)),
    );
  }

  @override
  bool shouldRepaint(_SpotPainter old) => old.center != center || old.color != color;
}

class _BorderPainter extends CustomPainter {
  _BorderPainter({
    required this.animation,
    required this.radius,
    required this.featured,
    required this.base,
    required this.glow,
    required this.hover,
  }) : super(repaint: animation);

  final Animation<double> animation;
  final double radius;
  final bool featured;
  final Color base;
  final Color glow;
  final bool hover;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).deflate(0.6);
    final rrect = RRect.fromRectAndRadius(rect, Radius.circular(radius));
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = featured ? 1.6 : 1.1;
    if (featured) {
      paint.shader = SweepGradient(
        colors: [glow, Brand.sky, glow.withValues(alpha: 0.15), Brand.amber, glow],
        stops: const [0.0, 0.25, 0.5, 0.75, 1.0],
        transform: GradientRotation(animation.value * 2 * math.pi),
      ).createShader(rect);
    } else {
      paint.shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          hover ? glow.withValues(alpha: 0.75) : base.withValues(alpha: 0.9),
          base.withValues(alpha: 0.35),
        ],
      ).createShader(rect);
    }
    canvas.drawRRect(rrect, paint);
  }

  @override
  bool shouldRepaint(_BorderPainter old) =>
      old.featured != featured || old.hover != hover || old.glow != glow || old.base != base;
}

// ---------------------------------------------------------------------------
// Distintivo de ajuste: forma + texto + color, nunca solo color
// ---------------------------------------------------------------------------

enum FitState { gpu, shared, spill, no }

FitState? fitStateFrom(String? value) => switch (value) {
      'gpu' => FitState.gpu,
      'shared' => FitState.shared,
      'spill' => FitState.spill,
      'no' => FitState.no,
      _ => null,
    };

class FitBadge extends StatelessWidget {
  const FitBadge(this.state, {super.key, this.label});
  final FitState state;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final (color, text) = switch (state) {
      FitState.gpu => (Brand.teal, 'Todo en GPU'),
      FitState.shared => (Brand.sky, 'Memoria compartida'),
      FitState.spill => (Brand.coral, 'Se desborda a RAM'),
      FitState.no => (Brand.rose, 'No cabe'),
    };
    return CustomPaint(
      painter: state == FitState.spill ? _HatchPainter(color) : null,
      child: Container(
        padding: const EdgeInsets.fromLTRB(7, 3, 9, 3),
        decoration: BoxDecoration(
          color: state == FitState.spill ? null : color.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(width: 12, height: 12, child: CustomPaint(painter: _FitIconPainter(state, color))),
          const SizedBox(width: 6),
          Text(label ?? text,
              style: TextStyle(color: color, fontSize: 11.5, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }
}

class _HatchPainter extends CustomPainter {
  _HatchPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(6));
    canvas.save();
    canvas.clipRRect(rrect);
    canvas.drawRect(Offset.zero & size, Paint()..color = color.withValues(alpha: 0.08));
    final stripe = Paint()
      ..color = color.withValues(alpha: 0.16)
      ..strokeWidth = 4;
    for (double x = -size.height; x < size.width + size.height; x += 10) {
      canvas.drawLine(Offset(x, size.height), Offset(x + size.height, 0), stripe);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_HatchPainter old) => old.color != color;
}

class _FitIconPainter extends CustomPainter {
  _FitIconPainter(this.state, this.color);
  final FitState state;
  final Color color;

  @override
  void paint(Canvas canvas, Size s) {
    final p = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.7
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    switch (state) {
      case FitState.gpu:
        canvas.drawPath(
            Path()
              ..moveTo(s.width * 0.18, s.height * 0.52)
              ..lineTo(s.width * 0.42, s.height * 0.74)
              ..lineTo(s.width * 0.82, s.height * 0.28),
            p);
      case FitState.shared:
        canvas.drawCircle(Offset(s.width * 0.36, s.height * 0.5), s.width * 0.24, p);
        canvas.drawCircle(Offset(s.width * 0.64, s.height * 0.5), s.width * 0.24, p);
      case FitState.spill:
        canvas.drawPath(
            Path()
              ..moveTo(s.width * 0.5, s.height * 0.12)
              ..lineTo(s.width * 0.92, s.height * 0.86)
              ..lineTo(s.width * 0.08, s.height * 0.86)
              ..close(),
            p);
        canvas.drawLine(Offset(s.width * 0.5, s.height * 0.42), Offset(s.width * 0.5, s.height * 0.6), p);
      case FitState.no:
        canvas.drawLine(Offset(s.width * 0.22, s.height * 0.22), Offset(s.width * 0.78, s.height * 0.78), p);
        canvas.drawLine(Offset(s.width * 0.78, s.height * 0.22), Offset(s.width * 0.22, s.height * 0.78), p);
    }
  }

  @override
  bool shouldRepaint(_FitIconPainter old) => old.state != state || old.color != color;
}

// ---------------------------------------------------------------------------
// Dónde corrió
// ---------------------------------------------------------------------------

class LocationChip extends StatelessWidget {
  const LocationChip(this.location, {super.key, this.providerName});
  final String location;
  final String? providerName;

  @override
  Widget build(BuildContext context) {
    final color = Brand.location(location);
    final (icon, text) = switch (location) {
      'local' => (context.icons.gpu, 'Este equipo'),
      'lan' => (context.icons.network, providerName ?? 'Tu red'),
      _ => (context.icons.cloud, providerName == null ? 'Sale de tu equipo' : '$providerName · sale de tu equipo'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.13),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 12, color: color),
        const SizedBox(width: 5),
        Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Anillo de créditos
// ---------------------------------------------------------------------------

/// Saldo como anillo ámbar: la proporción es contra el último paquete
/// comprado (o el bono mensual), para que "me queda poco" se vea sin leer cifras.
class CreditRing extends StatelessWidget {
  const CreditRing({super.key, required this.credits, required this.reference, this.size = 148});
  final double credits;
  final double reference;
  final double size;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final fraction = reference <= 0 ? 0.0 : (credits / reference).clamp(0.0, 1.0);
    final low = fraction < 0.15;
    return SizedBox(
      width: size,
      height: size,
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: fraction),
        duration: _reduceMotion(context) ? Duration.zero : const Duration(milliseconds: 900),
        curve: Curves.easeOutCubic,
        builder: (context, value, _) => CustomPaint(
          painter: _RingPainter(value, t.surfaceAlt, low ? Brand.coral : Brand.amber),
          child: Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(_compact(credits),
                  style: TextStyle(
                    color: t.text,
                    fontSize: size * 0.2,
                    fontWeight: FontWeight.w800,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    height: 1,
                  )),
              const SizedBox(height: 4),
              Text('créditos', style: t.small.copyWith(fontSize: 11.5)),
            ]),
          ),
        ),
      ),
    );
  }

  static String _compact(double v) {
    if (v >= 100000) return '${(v / 1000).toStringAsFixed(0)}k';
    if (v >= 10000) return '${(v / 1000).toStringAsFixed(1)}k';
    return v.toStringAsFixed(v >= 100 ? 0 : 1);
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.fraction, this.track, this.color);
  final double fraction;
  final Color track;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 11.0;
    final rect = (Offset.zero & size).deflate(stroke);
    canvas.drawArc(rect, 0, 2 * math.pi, false,
        Paint()
          ..color = track
          ..style = PaintingStyle.stroke
          ..strokeWidth = stroke);
    if (fraction <= 0) return;
    canvas.drawArc(
      rect,
      -math.pi / 2,
      2 * math.pi * fraction,
      false,
      Paint()
        ..shader = SweepGradient(
          colors: [color.withValues(alpha: 0.55), color, Brand.amberLight],
          transform: const GradientRotation(-math.pi / 2),
        ).createShader(rect)
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = stroke,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.fraction != fraction || old.color != color;
}
