import 'package:flutter/widgets.dart';

/// Breakpoints para que el entorno se ajuste bien al achicar la ventana.
enum ScreenSize { compact, medium, expanded }

class Breakpoints {
  Breakpoints._();
  static const double medium = 900;
  static const double expanded = 1200;

  static ScreenSize of(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    if (width < medium) return ScreenSize.compact;
    if (width < expanded) return ScreenSize.medium;
    return ScreenSize.expanded;
  }

  /// En compacto, la barra lateral se colapsa a solo iconos.
  static bool sidebarExpanded(BuildContext context) =>
      of(context) != ScreenSize.compact;
}
