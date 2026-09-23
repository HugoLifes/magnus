import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../domain/entities.dart';
import '../../domain/usecases.dart';

enum Status { initial, loading, success, failure }

// ----------------------------- Eventos -----------------------------
sealed class ModelsEvent extends Equatable {
  const ModelsEvent();
  @override
  List<Object?> get props => [];
}

class HardwareRequested extends ModelsEvent {
  const HardwareRequested();
}

class ModelsRequested extends ModelsEvent {
  const ModelsRequested();
}

class ModelSelected extends ModelsEvent {
  const ModelSelected(this.modelId);
  final String modelId;
  @override
  List<Object?> get props => [modelId];
}

class TargetSelected extends ModelsEvent {
  const TargetSelected(this.target);
  final String target;
  @override
  List<Object?> get props => [target];
}

class QuantMatrixRequested extends ModelsEvent {
  const QuantMatrixRequested();
}

// ----------------------------- Estado -----------------------------
class ModelsState extends Equatable {
  const ModelsState({
    this.hardwareStatus = Status.initial,
    this.gpus = const [],
    this.modelsStatus = Status.initial,
    this.models = const [],
    this.selectedModelId,
    this.selectedTarget = 'auto',
    this.matrixStatus = Status.initial,
    this.matrix = const [],
    this.failureMessage,
  });

  final Status hardwareStatus;
  final List<Gpu> gpus;
  final Status modelsStatus;
  final List<ModelSpec> models;
  final String? selectedModelId;
  final String selectedTarget;
  final Status matrixStatus;
  final List<Compatibility> matrix;
  final String? failureMessage;

  ModelsState copyWith({
    Status? hardwareStatus,
    List<Gpu>? gpus,
    Status? modelsStatus,
    List<ModelSpec>? models,
    String? selectedModelId,
    String? selectedTarget,
    Status? matrixStatus,
    List<Compatibility>? matrix,
    String? failureMessage,
  }) {
    return ModelsState(
      hardwareStatus: hardwareStatus ?? this.hardwareStatus,
      gpus: gpus ?? this.gpus,
      modelsStatus: modelsStatus ?? this.modelsStatus,
      models: models ?? this.models,
      selectedModelId: selectedModelId ?? this.selectedModelId,
      selectedTarget: selectedTarget ?? this.selectedTarget,
      matrixStatus: matrixStatus ?? this.matrixStatus,
      matrix: matrix ?? this.matrix,
      failureMessage: failureMessage,
    );
  }

  @override
  List<Object?> get props => [
        hardwareStatus, gpus, modelsStatus, models, selectedModelId,
        selectedTarget, matrixStatus, matrix, failureMessage,
      ];
}

// ----------------------------- BLoC -----------------------------
class ModelsBloc extends Bloc<ModelsEvent, ModelsState> {
  ModelsBloc({
    required GetHardware getHardware,
    required GetModels getModels,
    required GetQuantMatrix getQuantMatrix,
  })  : _getHardware = getHardware,
        _getModels = getModels,
        _getQuantMatrix = getQuantMatrix,
        super(const ModelsState()) {
    on<HardwareRequested>(_onHardware);
    on<ModelsRequested>(_onModels);
    on<ModelSelected>(_onModelSelected);
    on<TargetSelected>(_onTargetSelected);
    on<QuantMatrixRequested>(_onQuantMatrix);
  }

  final GetHardware _getHardware;
  final GetModels _getModels;
  final GetQuantMatrix _getQuantMatrix;

  Future<void> _onHardware(HardwareRequested e, Emitter<ModelsState> emit) async {
    emit(state.copyWith(hardwareStatus: Status.loading, failureMessage: null));
    try {
      final gpus = await _getHardware();
      emit(state.copyWith(hardwareStatus: Status.success, gpus: gpus));
    } on Failure catch (f) {
      emit(state.copyWith(hardwareStatus: Status.failure, failureMessage: f.message));
    }
  }

  Future<void> _onModels(ModelsRequested e, Emitter<ModelsState> emit) async {
    emit(state.copyWith(modelsStatus: Status.loading, failureMessage: null));
    try {
      final models = await _getModels();
      emit(state.copyWith(modelsStatus: Status.success, models: models));
    } on Failure catch (f) {
      emit(state.copyWith(modelsStatus: Status.failure, failureMessage: f.message));
    }
  }

  void _onModelSelected(ModelSelected e, Emitter<ModelsState> emit) {
    emit(state.copyWith(selectedModelId: e.modelId, matrix: const [], matrixStatus: Status.initial));
    add(const QuantMatrixRequested());
  }

  void _onTargetSelected(TargetSelected e, Emitter<ModelsState> emit) {
    emit(state.copyWith(selectedTarget: e.target));
    if (state.selectedModelId != null) add(const QuantMatrixRequested());
  }

  Future<void> _onQuantMatrix(QuantMatrixRequested e, Emitter<ModelsState> emit) async {
    final model = state.selectedModelId;
    if (model == null) return;
    emit(state.copyWith(matrixStatus: Status.loading, failureMessage: null));
    try {
      final matrix = await _getQuantMatrix(
        model: model,
        target: state.selectedTarget,
        context: 8192,
      );
      emit(state.copyWith(matrixStatus: Status.success, matrix: matrix));
    } on Failure catch (f) {
      emit(state.copyWith(matrixStatus: Status.failure, failureMessage: f.message));
    }
  }
}
