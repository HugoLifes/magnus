import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

class CloudState extends Equatable {
  const CloudState({
    this.presets = const [],
    this.providers = const [],
    this.tests = const {},
    this.account,
    this.packs = const [],
    this.loading = false,
    this.busy,
    this.error,
    this.notice,
  });

  final List<ProviderPreset> presets;
  final List<ProviderInfo> providers;

  /// Resultado de la última prueba por proveedor.
  final Map<String, ProviderTest> tests;
  final CloudAccount? account;
  final List<CreditPack> packs;
  final bool loading;

  /// Acción en curso ('connect:nvidia', 'test:spark', 'redeem'…), para el botón que la lanzó.
  final String? busy;
  final String? error;
  final String? notice;

  ProviderInfo? get cloud {
    for (final p in providers) {
      if (p.isCloud) return p;
    }
    return null;
  }

  ProviderInfo? byId(String id) {
    for (final p in providers) {
      if (p.id == id) return p;
    }
    return null;
  }

  ProviderPreset? preset(String kind) {
    for (final p in presets) {
      if (p.kind == kind) return p;
    }
    return null;
  }

  List<ProviderInfo> get servers => providers.where((p) => p.isServer).toList();

  CloudState copyWith({
    List<ProviderPreset>? presets,
    List<ProviderInfo>? providers,
    Map<String, ProviderTest>? tests,
    CloudAccount? account,
    bool clearAccount = false,
    List<CreditPack>? packs,
    bool? loading,
    String? busy,
    bool clearBusy = false,
    String? error,
    String? notice,
  }) =>
      CloudState(
        presets: presets ?? this.presets,
        providers: providers ?? this.providers,
        tests: tests ?? this.tests,
        account: clearAccount ? null : (account ?? this.account),
        packs: packs ?? this.packs,
        loading: loading ?? this.loading,
        busy: clearBusy ? null : (busy ?? this.busy),
        error: error,
        notice: notice,
      );

  @override
  List<Object?> get props =>
      [presets, providers, tests, account, packs, loading, busy, error, notice];
}

/// Nube opcional: servidores vLLM de la red, APIs con la clave del usuario y
/// Magnus Cloud con créditos. Todo pasa por el daemon; la app nunca ve una clave guardada.
class CloudCubit extends Cubit<CloudState> {
  CloudCubit(this._api) : super(const CloudState());

  final MagnusApi _api;

  Future<void> load() async {
    emit(state.copyWith(loading: true));
    try {
      final (presets, providers) = await _api.providers();
      emit(state.copyWith(loading: false, presets: presets, providers: providers));
    } on Failure catch (f) {
      emit(state.copyWith(loading: false, error: f.message));
      return;
    }
    await refreshAccount();
  }

  Future<void> refreshAccount() async {
    final cloud = state.cloud;
    if (cloud == null) {
      emit(state.copyWith(clearAccount: true, packs: const []));
      return;
    }
    try {
      final results = await Future.wait([_api.cloudAccount(cloud.id), _api.cloudPacks(cloud.id)]);
      emit(state.copyWith(
        account: results[0] as CloudAccount,
        packs: results[1] as List<CreditPack>,
      ));
    } on Failure catch (f) {
      emit(state.copyWith(error: 'Magnus Cloud: ${f.message}'));
    }
  }

  Future<void> _run(String busy, Future<String?> Function() action) async {
    if (state.busy != null) return;
    emit(state.copyWith(busy: busy));
    try {
      final notice = await action();
      emit(state.copyWith(clearBusy: true, notice: notice));
    } on Failure catch (f) {
      emit(state.copyWith(clearBusy: true, error: f.message));
    }
  }

  Future<void> connect(String id,
          {required String kind, String? name, String? baseUrl, String? apiKey}) =>
      _run('connect:$id', () async {
        final saved = await _api.saveProvider(id,
            kind: kind, name: name, baseUrl: baseUrl, apiKey: apiKey);
        final (_, providers) = await _api.providers();
        emit(state.copyWith(providers: providers, busy: 'connect:$id'));
        final test = await _api.testProvider(saved.id);
        emit(state.copyWith(tests: {...state.tests, saved.id: test}, busy: 'connect:$id'));
        if (saved.isCloud) await refreshAccount();
        return test.ok
            ? '${saved.name} conectado: ${test.models} modelo(s) disponibles.'
            : null;
      });

  Future<void> test(String id) => _run('test:$id', () async {
        final result = await _api.testProvider(id);
        emit(state.copyWith(tests: {...state.tests, id: result}, busy: 'test:$id'));
        return null;
      });

  Future<void> remove(String id) => _run('remove:$id', () async {
        final name = state.byId(id)?.name ?? id;
        await _api.deleteProvider(id);
        final (_, providers) = await _api.providers();
        final tests = {...state.tests}..remove(id);
        emit(state.copyWith(providers: providers, tests: tests, busy: 'remove:$id'));
        if (state.cloud == null) emit(state.copyWith(clearAccount: true, packs: const [], busy: 'remove:$id'));
        return '$name se quitó. Su clave se borró del llavero.';
      });

  Future<void> redeem(String code) => _run('redeem', () async {
        final cloud = state.cloud;
        if (cloud == null) throw const ServerFailure('Conecta Magnus Cloud primero.');
        if (code.trim().isEmpty) throw const ServerFailure('Escribe el código del vale.');
        final added = await _api.redeemCode(cloud.id, code.trim());
        await refreshAccount();
        return '+${_thousands(added)} créditos sumados a tu saldo.';
      });

  void dismiss() => emit(state.copyWith());

  void showNotice(String message) => emit(state.copyWith(notice: message));

  static String _thousands(int n) =>
      n.toString().replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');
}
