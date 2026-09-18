import 'package:equatable/equatable.dart';

/// GPU detectada en el host del daemon.
class Gpu extends Equatable {
  const Gpu({
    required this.index,
    required this.name,
    required this.totalGib,
    required this.freeGib,
  });

  final int index;
  final String name;
  final double totalGib;
  final double freeGib;

  @override
  List<Object?> get props => [index, name, totalGib, freeGib];
}

/// Modelo del registro del núcleo.
class ModelSpec extends Equatable {
  const ModelSpec({
    required this.id,
    required this.paramsB,
    required this.nLayers,
    required this.contextMax,
    required this.architecture,
    this.notes = '',
  });

  final String id;
  final double paramsB;
  final int nLayers;
  final int contextMax;
  final String architecture;
  final String notes;

  @override
  List<Object?> get props => [id, paramsB, nLayers, contextMax, architecture];
}

/// Veredicto de compatibilidad para un (modelo, cuant, destino).
class Compatibility extends Equatable {
  const Compatibility({
    required this.modelId,
    required this.quant,
    required this.context,
    required this.batch,
    required this.requiredGib,
    required this.availableGib,
    required this.weightsGib,
    required this.kvCacheGib,
    required this.fits,
    required this.headroomGib,
    required this.runtimes,
    required this.notes,
    this.recommendedQuant,
  });

  final String modelId;
  final String quant;
  final int context;
  final int batch;
  final double requiredGib;
  final double availableGib;
  final double weightsGib;
  final double kvCacheGib;
  final bool fits;
  final double headroomGib;
  final List<String> runtimes;
  final List<String> notes;
  final String? recommendedQuant;

  /// % de VRAM del destino usado (el núcleo no lo serializa; se calcula aquí).
  double get utilizationPct =>
      availableGib <= 0 ? 0 : (requiredGib / availableGib * 100);

  @override
  List<Object?> get props => [modelId, quant, requiredGib, availableGib, fits];
}
