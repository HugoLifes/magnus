/// Modelos de la API del daemon (JSON → Dart). Escritos a mano, como dtos.dart,
/// siguiendo el contrato de `daemon/app.py`.
library;

double _d(dynamic v) => (v as num?)?.toDouble() ?? 0.0;
double? _dn(dynamic v) => (v as num?)?.toDouble();
int _i(dynamic v) => (v as num?)?.toInt() ?? 0;
String _s(dynamic v, [String fallback = '']) => v?.toString() ?? fallback;
String? _sn(dynamic v) => v?.toString();
List<String> _ls(dynamic v) =>
    (v as List?)?.map((e) => e.toString()).toList() ?? const [];
Map<String, dynamic> _m(dynamic v) =>
    (v as Map?)?.cast<String, dynamic>() ?? const <String, dynamic>{};
List<Map<String, dynamic>> _lm(dynamic v) =>
    (v as List?)?.map(_m).toList() ?? const [];

// ---------------------------------------------------------------------------
// Plataforma y sistema
// ---------------------------------------------------------------------------

class HealthInfo {
  const HealthInfo({required this.ollama, this.ollamaVersion});
  final bool ollama;
  final String? ollamaVersion;

  factory HealthInfo.fromJson(Map<String, dynamic> j) =>
      HealthInfo(ollama: j['ollama'] == true, ollamaVersion: _sn(j['ollama_version']));
}

class PlatformInfo {
  const PlatformInfo({
    required this.family,
    required this.displayName,
    required this.unifiedMemory,
    required this.runtimes,
    required this.maxLoadedModels,
    required this.suggestedMaxParamsB,
    required this.gpuCount,
    required this.totalMemoryGib,
    required this.notes,
  });

  final String family;
  final String displayName;
  final bool unifiedMemory;
  final List<String> runtimes;
  final int maxLoadedModels;
  final double suggestedMaxParamsB;
  final int gpuCount;
  final double totalMemoryGib;
  final List<String> notes;

  /// Nombre legible de la familia NVIDIA.
  String get familyLabel => switch (family) {
        'jetson' => 'Jetson',
        'dgx-spark' => 'DGX Spark',
        'geforce-rtx' => 'GeForce RTX',
        'workstation' => 'RTX Workstation',
        'datacenter' => 'Datacenter',
        _ => 'Sin GPU NVIDIA',
      };

  factory PlatformInfo.fromJson(Map<String, dynamic> j) => PlatformInfo(
        family: _s(j['family'], 'unknown'),
        displayName: _s(j['display_name']),
        unifiedMemory: j['unified_memory'] == true,
        runtimes: _ls(j['runtimes']),
        maxLoadedModels: _i(j['max_loaded_models']),
        suggestedMaxParamsB: _d(j['suggested_max_params_b']),
        gpuCount: _i(j['gpu_count']),
        totalMemoryGib: _d(j['total_memory_gib']),
        notes: _ls(j['notes']),
      );
}

class GpuSample {
  const GpuSample({
    required this.index,
    required this.name,
    this.utilizationPct,
    this.powerW,
    this.temperatureC,
    this.memoryTotalGib,
    this.memoryUsedGib,
    this.unifiedMemory = false,
  });

  final int index;
  final String name;
  final double? utilizationPct;
  final double? powerW;
  final double? temperatureC;
  final double? memoryTotalGib;
  final double? memoryUsedGib;
  final bool unifiedMemory;

  factory GpuSample.fromJson(Map<String, dynamic> j) => GpuSample(
        index: _i(j['index']),
        name: _s(j['name'], 'GPU'),
        utilizationPct: _dn(j['utilization_pct']),
        powerW: _dn(j['power_w']),
        temperatureC: _dn(j['temperature_c']),
        memoryTotalGib: _dn(j['memory_total_gib']),
        memoryUsedGib: _dn(j['memory_used_gib']),
        unifiedMemory: j['unified_memory'] == true,
      );
}

class SystemSample {
  const SystemSample({
    required this.gpus,
    this.ramTotalGib,
    this.ramAvailableGib,
    this.boardPowerW,
    this.powerW,
  });

  final List<GpuSample> gpus;
  final double? ramTotalGib;
  final double? ramAvailableGib;
  final double? boardPowerW;
  final double? powerW;

  factory SystemSample.fromJson(Map<String, dynamic> j) => SystemSample(
        gpus: _lm(j['gpus']).map(GpuSample.fromJson).toList(),
        ramTotalGib: _dn(j['ram_total_gib']),
        ramAvailableGib: _dn(j['ram_available_gib']),
        boardPowerW: _dn(j['board_power_w']),
        powerW: _dn(j['power_w']),
      );
}

// ---------------------------------------------------------------------------
// Medidor
// ---------------------------------------------------------------------------

class TurnMetrics {
  const TurnMetrics({
    required this.model,
    required this.tokensIn,
    required this.tokensOut,
    required this.durationS,
    this.ttftS,
    this.tokensPerS,
    this.avgPowerW,
    this.energyWh,
    required this.localCostUsd,
    required this.cloudReference,
    required this.cloudCostUsd,
    required this.savingsUsd,
    this.provider = 'local',
    this.location = 'local',
    this.providerCostUsd,
  });

  final String model;
  final int tokensIn;
  final int tokensOut;
  final double durationS;
  final double? ttftS;
  final double? tokensPerS;
  final double? avgPowerW;
  final double? energyWh;
  final double localCostUsd;
  final String cloudReference;
  final double cloudCostUsd;
  final double savingsUsd;

  /// Dónde corrió: 'local' (este equipo), 'lan' (servidor en tu red) o 'cloud'.
  final String provider;
  final String location;

  /// Lo que cobró el proveedor remoto; null si fue gratis o no se sabe.
  final double? providerCostUsd;

  bool get isRemote => location != 'local';

  factory TurnMetrics.fromJson(Map<String, dynamic> j) => TurnMetrics(
        model: _s(j['model']),
        tokensIn: _i(j['tokens_in']),
        tokensOut: _i(j['tokens_out']),
        durationS: _d(j['duration_s']),
        ttftS: _dn(j['ttft_s']),
        tokensPerS: _dn(j['tokens_per_s']),
        avgPowerW: _dn(j['avg_power_w']),
        energyWh: _dn(j['energy_wh']),
        localCostUsd: _d(j['local_cost_usd']),
        cloudReference: _s(j['cloud_reference']),
        cloudCostUsd: _d(j['cloud_cost_usd']),
        savingsUsd: _d(j['savings_usd']),
        provider: _s(j['provider'], 'local'),
        location: _s(j['location'], 'local'),
        providerCostUsd: _dn(j['provider_cost_usd']),
      );
}

class UsageSummary {
  const UsageSummary({
    required this.turns,
    required this.tokensIn,
    required this.tokensOut,
    required this.energyWh,
    required this.localCostUsd,
    required this.cloudCostUsd,
    required this.savingsUsd,
    this.byModel = const [],
    this.model = '',
  });

  final int turns;
  final int tokensIn;
  final int tokensOut;
  final double energyWh;
  final double localCostUsd;
  final double cloudCostUsd;
  final double savingsUsd;
  final List<UsageSummary> byModel;
  final String model;

  factory UsageSummary.fromJson(Map<String, dynamic> j) => UsageSummary(
        turns: _i(j['turns']),
        tokensIn: _i(j['tokens_in']),
        tokensOut: _i(j['tokens_out']),
        energyWh: _d(j['energy_wh']),
        localCostUsd: _d(j['local_cost_usd']),
        cloudCostUsd: _d(j['cloud_cost_usd']),
        savingsUsd: _d(j['savings_usd']),
        byModel: _lm(j['by_model']).map(UsageSummary.fromJson).toList(),
        model: _s(j['model']),
      );
}

// ---------------------------------------------------------------------------
// Modelos
// ---------------------------------------------------------------------------

class CatalogEntry {
  const CatalogEntry({
    required this.id,
    required this.name,
    required this.paramsB,
    required this.sizeGib,
    required this.capabilities,
    required this.context,
    required this.license,
    required this.description,
    required this.requiredGib,
    required this.fits,
    this.note,
  });

  final String id;
  final String name;
  final double paramsB;
  final double sizeGib;
  final List<String> capabilities;
  final int context;
  final String license;
  final String description;
  final double requiredGib;
  final bool fits;
  final String? note;

  factory CatalogEntry.fromJson(Map<String, dynamic> j) => CatalogEntry(
        id: _s(j['id']),
        name: _s(j['name']),
        paramsB: _d(j['params_b']),
        sizeGib: _d(j['size_gib']),
        capabilities: _ls(j['capabilities']),
        context: _i(j['context']),
        license: _s(j['license']),
        description: _s(j['description']),
        requiredGib: _d(j['required_gib']),
        fits: j['fits'] == true,
        note: _sn(j['note']),
      );
}

class CatalogInfo {
  const CatalogInfo({required this.family, required this.usableGib, required this.models});
  final String family;
  final double usableGib;
  final List<CatalogEntry> models;

  factory CatalogInfo.fromJson(Map<String, dynamic> j) => CatalogInfo(
        family: _s(j['family']),
        usableGib: _d(j['usable_gib']),
        models: _lm(j['models']).map(CatalogEntry.fromJson).toList(),
      );
}

class LocalModel {
  const LocalModel({required this.modelId, this.sizeGib, this.parameterSize, this.quantization});
  final String modelId;
  final double? sizeGib;
  final String? parameterSize;
  final String? quantization;

  factory LocalModel.fromJson(Map<String, dynamic> j) => LocalModel(
        modelId: _s(j['model_id']),
        sizeGib: _dn(j['size_gib']),
        parameterSize: _sn(j['parameter_size']),
        quantization: _sn(j['quantization']),
      );
}

class LoadedModel {
  const LoadedModel({required this.modelId, this.sizeVramGib, this.notes = const []});
  final String modelId;
  final double? sizeVramGib;
  final List<String> notes;

  factory LoadedModel.fromJson(Map<String, dynamic> j) => LoadedModel(
        modelId: _s(j['model_id']),
        sizeVramGib: _dn(j['size_vram_gib']),
        notes: _ls(j['notes']),
      );
}

class PullProgress {
  const PullProgress({required this.status, this.completed, this.total, this.percent, this.detail});
  final String status;
  final int? completed;
  final int? total;
  final double? percent;
  final String? detail;

  bool get isDone => status == 'success';
  bool get isError => status == 'error';

  factory PullProgress.fromJson(Map<String, dynamic> j) => PullProgress(
        status: _s(j['status']),
        completed: (j['completed'] as num?)?.toInt(),
        total: (j['total'] as num?)?.toInt(),
        percent: _dn(j['percent']),
        detail: _sn(j['detail']),
      );
}

// ---------------------------------------------------------------------------
// Conversaciones
// ---------------------------------------------------------------------------

class ConversationInfo {
  const ConversationInfo({required this.id, required this.title, required this.model});
  final String id;
  final String title;
  final String model;

  factory ConversationInfo.fromJson(Map<String, dynamic> j) =>
      ConversationInfo(id: _s(j['id']), title: _s(j['title']), model: _s(j['model']));
}

class StoredMessage {
  const StoredMessage({required this.role, required this.content, this.metrics});
  final String role;
  final String content;
  final TurnMetrics? metrics;

  factory StoredMessage.fromJson(Map<String, dynamic> j) => StoredMessage(
        role: _s(j['role']),
        content: _s(j['content']),
        metrics: j['metrics'] is Map ? TurnMetrics.fromJson(_m(j['metrics'])) : null,
      );
}

// ---------------------------------------------------------------------------
// Documentos y memoria
// ---------------------------------------------------------------------------

class CollectionInfo {
  const CollectionInfo({
    required this.name,
    required this.embeddingModel,
    required this.chunkChars,
    required this.overlapChars,
    required this.documents,
    required this.chunks,
  });

  final String name;
  final String embeddingModel;
  final int chunkChars;
  final int overlapChars;
  final int documents;
  final int chunks;

  factory CollectionInfo.fromJson(Map<String, dynamic> j) => CollectionInfo(
        name: _s(j['name']),
        embeddingModel: _s(j['embedding_model']),
        chunkChars: _i(j['chunk_chars']),
        overlapChars: _i(j['overlap_chars']),
        documents: _i(j['documents']),
        chunks: _i(j['chunks']),
      );
}

class DocumentInfo {
  const DocumentInfo({required this.id, required this.title, required this.source, required this.chunks});
  final String id;
  final String title;
  final String source;
  final int chunks;

  factory DocumentInfo.fromJson(Map<String, dynamic> j) => DocumentInfo(
        id: _s(j['id']),
        title: _s(j['title']),
        source: _s(j['source']),
        chunks: _i(j['chunks']),
      );
}

class SearchHit {
  const SearchHit({required this.score, required this.text, required this.title});
  final double score;
  final String text;
  final String title;

  factory SearchHit.fromJson(Map<String, dynamic> j) =>
      SearchHit(score: _d(j['score']), text: _s(j['text']), title: _s(j['title']));
}

class IngestResult {
  const IngestResult({required this.indexed, required this.skipped, required this.chunks, required this.errors});
  final int indexed;
  final int skipped;
  final int chunks;
  final Map<String, String> errors;

  factory IngestResult.fromJson(Map<String, dynamic> j) => IngestResult(
        indexed: _i(j['indexed']),
        skipped: _i(j['skipped']),
        chunks: _i(j['chunks']),
        errors: _m(j['errors']).map((k, v) => MapEntry(k, v.toString())),
      );
}

class MemoryItem {
  const MemoryItem({required this.id, required this.text});
  final int id;
  final String text;

  factory MemoryItem.fromJson(Map<String, dynamic> j) =>
      MemoryItem(id: _i(j['id']), text: _s(j['text']));
}

// ---------------------------------------------------------------------------
// Skills y agentes
// ---------------------------------------------------------------------------

class SkillInfo {
  const SkillInfo({
    required this.name,
    required this.description,
    required this.triggers,
    required this.source,
    this.body,
  });

  final String name;
  final String description;
  final List<String> triggers;
  final String source;
  final String? body;

  bool get builtin => source == 'builtin';

  factory SkillInfo.fromJson(Map<String, dynamic> j) => SkillInfo(
        name: _s(j['name']),
        description: _s(j['description']),
        triggers: _ls(j['triggers']),
        source: _s(j['source'], 'user'),
        body: _sn(j['body']),
      );
}

class ToolInfo {
  const ToolInfo({required this.name, required this.description});
  final String name;
  final String description;

  factory ToolInfo.fromJson(Map<String, dynamic> j) =>
      ToolInfo(name: _s(j['name']), description: _s(j['description']));
}

class AgentInfo {
  const AgentInfo({
    required this.name,
    required this.description,
    this.system = '',
    this.model,
    this.skills = const [],
    this.tools = const [],
    this.collection,
    this.maxSteps = 6,
    this.maxOutputTokens = 4000,
    this.think,
    this.source = 'user',
  });

  final String name;
  final String description;
  final String system;
  final String? model;
  final List<String> skills;
  final List<String> tools;
  final String? collection;
  final int maxSteps;
  final int maxOutputTokens;
  final bool? think;
  final String source;

  bool get builtin => source == 'builtin';

  factory AgentInfo.fromJson(Map<String, dynamic> j) => AgentInfo(
        name: _s(j['name']),
        description: _s(j['description']),
        system: _s(j['system']),
        model: _sn(j['model']),
        skills: _ls(j['skills']),
        tools: _ls(j['tools']),
        collection: _sn(j['collection']),
        maxSteps: _i(j['max_steps']),
        maxOutputTokens: _i(j['max_output_tokens']),
        think: j['think'] as bool?,
        source: _s(j['source'], 'user'),
      );

  /// Cuerpo de `PUT /agents/{name}`.
  Map<String, dynamic> toBody() => {
        'description': description,
        'system': system,
        'model': model,
        'skills': skills,
        'tools': tools,
        'collection': collection,
        'max_steps': maxSteps,
        'max_output_tokens': maxOutputTokens,
        'think': think,
      };
}

// ---------------------------------------------------------------------------
// Ajustes del daemon
// ---------------------------------------------------------------------------

class DaemonSettings {
  const DaemonSettings({
    required this.electricityUsdPerKwh,
    this.hardwareCostUsd,
    required this.hardwareLifetimeYears,
    required this.hoursPerDay,
    required this.cloudReference,
    required this.persona,
  });

  final double electricityUsdPerKwh;
  final double? hardwareCostUsd;
  final double hardwareLifetimeYears;
  final double hoursPerDay;
  final String cloudReference;

  /// Cómo habla Magnus en el chat (ver /personas).
  final String persona;

  factory DaemonSettings.fromJson(Map<String, dynamic> j) => DaemonSettings(
        electricityUsdPerKwh: _d(j['electricity_usd_per_kwh']),
        hardwareCostUsd: _dn(j['hardware_cost_usd']),
        hardwareLifetimeYears: _d(j['hardware_lifetime_years']),
        hoursPerDay: _d(j['hours_per_day']),
        cloudReference: _s(j['cloud_reference'], 'auto'),
        persona: _s(j['persona'], 'magnus'),
      );
}

/// Una forma de hablar del asistente.
class PersonaInfo {
  const PersonaInfo({required this.id, required this.name, required this.tagline});

  final String id;
  final String name;
  final String tagline;

  factory PersonaInfo.fromJson(Map<String, dynamic> j) => PersonaInfo(
        id: _s(j['id'], ''),
        name: _s(j['name'], ''),
        tagline: _s(j['tagline'], ''),
      );
}

/// Plan de este equipo y qué desbloquea.
class LicenseInfo {
  const LicenseInfo({
    required this.plan,
    required this.effectivePlan,
    required this.holder,
    required this.status,
    this.daysLeft,
    required this.features,
  });

  final String plan;
  final String effectivePlan;
  final String holder;
  final String status;
  final int? daysLeft;
  final Map<String, bool> features;

  bool get isPro => effectivePlan != 'community';

  factory LicenseInfo.fromJson(Map<String, dynamic> j) {
    final lic = (j['license'] as Map?)?.cast<String, dynamic>() ?? const {};
    final feats = (j['features'] as Map?)?.cast<String, dynamic>() ?? const {};
    return LicenseInfo(
      plan: _s(lic['plan'], 'community'),
      effectivePlan: _s(lic['effective_plan'], 'community'),
      holder: _s(lic['holder'], ''),
      status: _s(lic['status'], 'activa'),
      daysLeft: lic['days_left'] == null ? null : (lic['days_left'] as num).toInt(),
      features: {for (final e in feats.entries) e.key: e.value == true},
    );
  }
}

// ---------------------------------------------------------------------------
// Proveedores externos y Magnus Cloud
// ---------------------------------------------------------------------------

/// Tipo de proveedor que ofrece el daemon (vLLM, NVIDIA API, Groq…).
class ProviderPreset {
  const ProviderPreset({
    required this.kind,
    required this.label,
    required this.baseUrl,
    required this.needsKey,
    this.keyUrl,
    required this.notice,
    required this.description,
  });

  final String kind;
  final String label;
  final String baseUrl;
  final bool needsKey;
  final String? keyUrl;
  final String notice;
  final String description;

  factory ProviderPreset.fromJson(Map<String, dynamic> j) => ProviderPreset(
        kind: _s(j['kind']),
        label: _s(j['label']),
        baseUrl: _s(j['base_url']),
        needsKey: j['needs_key'] == true,
        keyUrl: _sn(j['key_url']),
        notice: _s(j['notice']),
        description: _s(j['description']),
      );
}

/// Proveedor configurado. La clave nunca viaja de vuelta: solo `hasKey`.
class ProviderInfo {
  const ProviderInfo({
    required this.id,
    required this.kind,
    required this.name,
    required this.baseUrl,
    required this.enabled,
    required this.location,
    required this.hasKey,
    this.defaultModel,
    this.notice = '',
  });

  final String id;
  final String kind;
  final String name;
  final String baseUrl;
  final bool enabled;
  final String location;
  final bool hasKey;
  final String? defaultModel;
  final String notice;

  bool get isCloud => kind == 'magnus-cloud';
  bool get isServer => kind == 'vllm' || kind == 'openai-compatible';

  factory ProviderInfo.fromJson(Map<String, dynamic> j) => ProviderInfo(
        id: _s(j['id']),
        kind: _s(j['kind']),
        name: _s(j['name']),
        baseUrl: _s(j['base_url']),
        enabled: j['enabled'] != false,
        location: _s(j['location'], 'cloud'),
        hasKey: j['has_key'] == true,
        defaultModel: _sn(j['default_model']),
        notice: _s(j['notice']),
      );
}

class ProviderTest {
  const ProviderTest({required this.ok, this.detail, this.models = 0, this.sample = const []});
  final bool ok;
  final String? detail;
  final int models;
  final List<String> sample;

  factory ProviderTest.fromJson(Map<String, dynamic> j) => ProviderTest(
        ok: j['ok'] == true,
        detail: _sn(j['detail']),
        models: _i(j['models']),
        sample: _ls(j['sample']),
      );
}

class CreditPack {
  const CreditPack({
    required this.id,
    required this.name,
    required this.priceUsd,
    required this.credits,
    required this.bonusPct,
    required this.tagline,
    required this.featured,
    this.approxTokens,
    this.referenceModel,
  });

  final String id;
  final String name;
  final double priceUsd;
  final int credits;
  final int bonusPct;
  final String tagline;
  final bool featured;
  final int? approxTokens;
  final String? referenceModel;

  factory CreditPack.fromJson(Map<String, dynamic> j) => CreditPack(
        id: _s(j['id']),
        name: _s(j['name']),
        priceUsd: _d(j['price_usd']),
        credits: _i(j['credits']),
        bonusPct: _i(j['bonus_pct']),
        tagline: _s(j['tagline']),
        featured: j['featured'] == true,
        approxTokens: (j['approx_tokens'] as num?)?.toInt(),
        referenceModel: _sn(j['reference_model']),
      );
}

class CreditMovement {
  const CreditMovement({
    required this.kind,
    required this.credits,
    required this.ref,
    this.meta = const {},
    required this.createdAt,
  });

  final String kind; // grant | topup | debit | adjust
  final double credits;
  final String ref;
  final Map<String, dynamic> meta;
  final double createdAt;

  factory CreditMovement.fromJson(Map<String, dynamic> j) => CreditMovement(
        kind: _s(j['kind']),
        credits: _d(j['credits']),
        ref: _s(j['ref']),
        meta: _m(j['meta']),
        createdAt: _d(j['created_at']),
      );
}

class CloudAccount {
  const CloudAccount({
    required this.name,
    required this.balanceCredits,
    required this.balanceUsd,
    required this.freeMonthlyCredits,
    this.history = const [],
  });

  final String name;
  final double balanceCredits;
  final double balanceUsd;
  final int freeMonthlyCredits;
  final List<CreditMovement> history;

  factory CloudAccount.fromJson(Map<String, dynamic> j) => CloudAccount(
        name: _s(_m(j['account'])['name']),
        balanceCredits: _d(j['balance_credits']),
        balanceUsd: _d(j['balance_usd']),
        freeMonthlyCredits: _i(j['free_monthly_credits']),
        history: _lm(j['history']).map(CreditMovement.fromJson).toList(),
      );
}
