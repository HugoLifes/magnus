import 'entities.dart';
import 'repositories/magnus_repository.dart';

/// Casos de uso — una intención de negocio por clase. Mantienen la presentación
/// ignorante de la capa de datos. Todos delegan en el repositorio.

class GetHardware {
  const GetHardware(this._repo);
  final MagnusRepository _repo;
  Future<List<Gpu>> call() => _repo.getHardware();
}

class GetModels {
  const GetModels(this._repo);
  final MagnusRepository _repo;
  Future<List<ModelSpec>> call() => _repo.getModels();
}

class CheckCompatibility {
  const CheckCompatibility(this._repo);
  final MagnusRepository _repo;
  Future<Compatibility> call({
    required String model,
    required String target,
    required String quant,
    int? context,
    int batch = 1,
  }) =>
      _repo.checkCompatibility(
        model: model,
        target: target,
        quant: quant,
        context: context,
        batch: batch,
      );
}

class GetQuantMatrix {
  const GetQuantMatrix(this._repo);
  final MagnusRepository _repo;
  Future<List<Compatibility>> call({
    required String model,
    required String target,
    int? context,
    int batch = 1,
  }) =>
      _repo.getQuantMatrix(
        model: model,
        target: target,
        context: context,
        batch: batch,
      );
}
