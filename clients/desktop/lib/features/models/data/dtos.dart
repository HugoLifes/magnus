import '../domain/entities.dart';

/// DTOs: traducen el JSON del daemon a entidades de dominio. Se escriben a mano
/// (sin codegen) para mantener el scaffold simple. Si crece, migrar a freezed.

double _toDouble(dynamic v) => (v as num?)?.toDouble() ?? 0.0;
int _toInt(dynamic v) => (v as num?)?.toInt() ?? 0;

class GpuDto {
  static Gpu fromJson(Map<String, dynamic> j) => Gpu(
        index: _toInt(j['index']),
        name: j['name'] as String? ?? 'GPU',
        totalGib: _toDouble(j['total_gib']),
        freeGib: _toDouble(j['free_gib']),
      );
}

class ModelSpecDto {
  static ModelSpec fromJson(Map<String, dynamic> j) => ModelSpec(
        id: j['id'] as String,
        paramsB: _toDouble(j['params_b']),
        nLayers: _toInt(j['n_layers']),
        contextMax: _toInt(j['context_max']),
        architecture: j['architecture'] as String? ?? '',
        notes: j['notes'] as String? ?? '',
      );
}

class CompatibilityDto {
  static Compatibility fromJson(Map<String, dynamic> j) => Compatibility(
        modelId: j['model_id'] as String? ?? '',
        quant: j['quant'] as String? ?? '',
        context: _toInt(j['context']),
        batch: _toInt(j['batch']),
        requiredGib: _toDouble(j['required_gib']),
        availableGib: _toDouble(j['available_gib']),
        weightsGib: _toDouble(j['weights_gib']),
        kvCacheGib: _toDouble(j['kv_cache_gib']),
        fits: j['fits'] as bool? ?? false,
        headroomGib: _toDouble(j['headroom_gib']),
        runtimes: (j['runtimes'] as List?)?.map((e) => e.toString()).toList() ?? const [],
        notes: (j['notes'] as List?)?.map((e) => e.toString()).toList() ?? const [],
        recommendedQuant: j['recommended_quant'] as String?,
      );
}
