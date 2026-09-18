import '../../domain/entities.dart';
import '../../domain/repositories/magnus_repository.dart';
import '../datasources/magnus_remote_datasource.dart';

/// Implementación del repositorio. Hoy solo hay una fuente remota; si mañana se
/// añade caché local, se compone aquí sin tocar dominio ni presentación.
class MagnusRepositoryImpl implements MagnusRepository {
  MagnusRepositoryImpl(this._remote);
  final MagnusRemoteDataSource _remote;

  @override
  Future<List<Gpu>> getHardware() => _remote.getHardware();

  @override
  Future<List<ModelSpec>> getModels() => _remote.getModels();

  @override
  Future<Compatibility> checkCompatibility({
    required String model,
    required String target,
    required String quant,
    int? context,
    int batch = 1,
  }) =>
      _remote.checkCompatibility(
        model: model,
        target: target,
        quant: quant,
        context: context,
        batch: batch,
      );

  @override
  Future<List<Compatibility>> getQuantMatrix({
    required String model,
    required String target,
    int? context,
    int batch = 1,
  }) =>
      _remote.getQuantMatrix(
        model: model,
        target: target,
        context: context,
        batch: batch,
      );
}
