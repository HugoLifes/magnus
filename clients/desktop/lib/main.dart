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
