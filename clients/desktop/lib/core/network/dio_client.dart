import 'package:dio/dio.dart';

import '../constants.dart';

/// Envoltorio fino sobre Dio apuntando al daemon de Magnus. La URL base y el
/// token son mutables porque se cambian en Ajustes sin reiniciar la app.
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
  String? _token;

  set baseUrl(String url) => dio.options.baseUrl = url;
  String get baseUrl => dio.options.baseUrl;

  /// Token de acceso del daemon (solo hace falta si escucha fuera de loopback).
  String? get token => _token;
  set token(String? value) {
    _token = (value == null || value.trim().isEmpty) ? null : value.trim();
    if (_token == null) {
      dio.options.headers.remove('Authorization');
    } else {
      dio.options.headers['Authorization'] = 'Bearer $_token';
    }
  }
}
