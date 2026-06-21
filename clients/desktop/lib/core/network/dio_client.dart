import 'package:dio/dio.dart';

import '../constants.dart';

/// Envoltorio fino sobre Dio apuntando al daemon de Magnus. La URL base es
/// mutable porque se puede cambiar en Ajustes sin reiniciar la app.
class DioClient {
  DioClient({String? baseUrl})
      : dio = Dio(
          BaseOptions(
            baseUrl: baseUrl ?? AppConstants.defaultDaemonUrl,
            connectTimeout: const Duration(seconds: 5),
            receiveTimeout: const Duration(seconds: 20),
            headers: {'Content-Type': 'application/json'},
          ),
        );

  final Dio dio;

  set baseUrl(String url) => dio.options.baseUrl = url;
  String get baseUrl => dio.options.baseUrl;
}
