import 'package:dio/dio.dart';

import '../../../../core/constants.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/dio_client.dart';
import '../../domain/entities.dart';
import '../dtos.dart';

/// Única clase que habla HTTP con el daemon. Mapea errores de Dio a Failures.
class MagnusRemoteDataSource {
  MagnusRemoteDataSource(this._client);
  final DioClient _client;

  Future<List<Gpu>> getHardware() => _guard(() async {
        final res = await _client.dio.get<Map<String, dynamic>>('/hardware');
        final list = (res.data?['gpus'] as List?) ?? const [];
        return list.map((e) => GpuDto.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<List<ModelSpec>> getModels() => _guard(() async {
        final res = await _client.dio.get<Map<String, dynamic>>('/models');
        final list = (res.data?['models'] as List?) ?? const [];
        return list.map((e) => ModelSpecDto.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<Compatibility> checkCompatibility({
    required String model,
    required String target,
    required String quant,
    int? context,
    int batch = 1,
  }) =>
      _guard(() async {
        final res = await _client.dio.post<Map<String, dynamic>>(
          '/compatibility',
          data: {
            'model': model,
            'target': target,
            'quant': quant,
            'context': context,
            'batch': batch,
          },
        );
        return CompatibilityDto.fromJson(res.data!);
      });

  /// El daemon aún no expone /quants; construimos la matriz llamando a
  /// /compatibility por cada cuant (ver ROADMAP: exponer /quants en Fase 1).
  Future<List<Compatibility>> getQuantMatrix({
    required String model,
    required String target,
    int? context,
    int batch = 1,
  }) async {
    final results = await Future.wait(
      AppConstants.quants.map(
        (q) => checkCompatibility(
          model: model,
          target: target,
          quant: q,
          context: context,
          batch: batch,
        ),
      ),
    );
    return results;
  }

  /// Centraliza el mapeo de errores de Dio a Failures de dominio.
  Future<T> _guard<T>(Future<T> Function() body) async {
    try {
      return await body();
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        throw ConnectionFailure(
            'No se pudo conectar a ${_client.baseUrl}. ¿Está corriendo `magnus serve`?');
      }
      final detail = e.response?.data is Map ? e.response?.data['detail'] : null;
      throw ServerFailure(detail?.toString() ?? 'Error ${e.response?.statusCode ?? ''} del daemon.');
    } catch (_) {
      throw const ParseFailure();
    }
  }
}
