import '../entities.dart';

/// Contrato del dominio. La presentación depende de esta abstracción, no de Dio.
abstract interface class MagnusRepository {
  Future<List<Gpu>> getHardware();

  Future<List<ModelSpec>> getModels();

  Future<Compatibility> checkCompatibility({
    required String model,
    required String target,
    required String quant,
    int? context,
    int batch = 1,
  });

  /// Matriz de cuantizaciones: evalúa todas las cuants para un (modelo, destino).
  Future<List<Compatibility>> getQuantMatrix({
    required String model,
    required String target,
    int? context,
    int batch = 1,
  });
}
