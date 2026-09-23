import 'package:flutter/widgets.dart';

import '../../core/theme/magnus_theme.dart';

/// Bloques grises con un brillo que los recorre mientras llegan los datos.
///
/// Un «Cargando…» dice que esperes; un esqueleto dice **qué** estás esperando y
/// cuánto va a ocupar, así que la pantalla no salta cuando por fin llega. En
/// Magnus además el daemon a veces tarda de verdad (arrancar Ollama, leer
/// sensores), así que esta espera se ve a menudo y conviene que se vea bien.
///
/// Respeta «reducir movimiento» del sistema: sin animación se queda el bloque
/// quieto, que sigue comunicando lo mismo.
class Skeleton extends StatefulWidget {
  const Skeleton({super.key, this.width, this.height = 14, this.radius});

  final double? width;
  final double height;
  final double? radius;

  /// Varias líneas de alto de texto, la última más corta, como un párrafo real.
  static Widget lines(int count, {double spacing = 8, double? width}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < count; i++) ...[
            if (i > 0) SizedBox(height: spacing),
            Skeleton(width: i == count - 1 ? (width ?? 220) * 0.6 : width),
          ],
        ],
      );

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reducir = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (reducir) {
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
    final base = t.surfaceAlt;
    final brillo = t.isDark ? const Color(0x14FFFFFF) : const Color(0x0F000000);
    return SizedBox(
      width: widget.width,
      height: widget.height,
      child: AnimatedBuilder(
        animation: _c,
        builder: (context, _) => DecoratedBox(
          decoration: BoxDecoration(
            color: base,
            borderRadius: BorderRadius.circular(widget.radius ?? widget.height / 2),
            gradient: _c.isAnimating
                ? LinearGradient(
                    begin: Alignment(-1 - 2 * (1 - _c.value), 0),
                    end: Alignment(1 - 2 * (1 - _c.value), 0),
                    colors: [base, brillo, base],
                  )
                : null,
          ),
        ),
      ),
    );
  }
}
