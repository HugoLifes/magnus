import 'package:flutter/widgets.dart';
import 'package:flutter_acrylic/flutter_acrylic.dart';
import 'package:window_manager/window_manager.dart';

import 'app.dart';
import 'core/constants.dart';
import 'core/di/injector.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Inyección de dependencias (DI) antes de arrancar la UI.
  await initDependencies();

  // Ventana nativa: tamaño mínimo para que el entorno se ajuste bien al achicar.
  await windowManager.ensureInitialized();
  await Window.initialize(); // flutter_acrylic
  // Fondo translúcido nativo (glassmorphism) para el diseño Windows.
  // Si el SO no lo soporta, los shells siguen pintando su propio fondo.
  try {
    await Window.setEffect(
      effect: WindowEffect.acrylic,
      color: const Color(0xCC0D0A18),
      dark: true,
    );
  } catch (_) {
    // sin soporte de efecto: continuar con fondo opaco del shell
  }
  const options = WindowOptions(
    size: Size(1180, 760),
    minimumSize: Size(AppConstants.minWindowWidth, AppConstants.minWindowHeight),
    center: true,
    title: 'Magnus',
  );
  await windowManager.waitUntilReadyToShow(options, () async {
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(const MagnusApp());
}
