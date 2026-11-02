// Configure the teacher firmware's observed memory map and Cortex-M vector entries.
// @category Firmware
// Arguments: [vector_base_hex] [vector_word_count_decimal]
import java.math.BigInteger;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.DWordDataType;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.SourceType;

public class PrepareSTM32 extends GhidraScript {
    private void mapUninitialized(String name, long start, long length, boolean isVolatile)
            throws Exception {
        Memory memory = currentProgram.getMemory();
        Address first = toAddr(start);
        Address last = first.add(length - 1);
        if (memory.intersects(first, last)) {
            println("Existing memory intersects " + name + "; preserving existing mapping.");
            return;
        }
        MemoryBlock block = memory.createUninitializedBlock(name, first, length, false);
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(false);
        block.setVolatile(isVolatile);
        block.setComment("Analysis-only address mapping; no bytes read from hardware.");
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        long vectorBase = args.length > 0 ? Long.decode(args[0]) : 0x70100400L;
        int vectorWords = args.length > 1 ? Integer.parseInt(args[1]) : 211;
        if (!currentProgram.getLanguageID().toString().equals("ARM:LE:32:v8-m")) {
            throw new IllegalArgumentException("Use -processor ARM:LE:32:v8-m -cspec default");
        }
        Memory memory = currentProgram.getMemory();
        Register thumb = currentProgram.getRegister("TMode");
        for (MemoryBlock block : memory.getBlocks()) {
            if (block.isInitialized()) {
                block.setRead(true);
                block.setWrite(false);
                block.setExecute(true);
                if (thumb != null) {
                    currentProgram.getProgramContext().setValue(
                        thumb, block.getStart(), block.getEnd(), BigInteger.ONE);
                }
            }
        }
        mapUninitialized("SRAM_AXI", 0x34000000L, 0x200000L, false);
        mapUninitialized("PERIPHERALS", 0x40000000L, 0x20000000L, true);
        mapUninitialized("SYSTEM_CONTROL", 0xe0000000L, 0x100000L, true);

        Address table = toAddr(vectorBase);
        long[] values = new long[vectorWords];
        Map<Long, Integer> frequency = new HashMap<>();
        for (int i = 0; i < vectorWords; i++) {
            monitor.checkCancelled();
            values[i] = Integer.toUnsignedLong(memory.getInt(table.add(i * 4L)));
            if (i > 0 && (values[i] & 1) != 0 && values[i] != 0xffffffffL) {
                long target = values[i] & ~1L;
                frequency.put(target, frequency.getOrDefault(target, 0) + 1);
            }
        }
        createLabel(table, "VectorTable", true);
        Set<Long> seeded = new HashSet<>();
        String[] exceptions = {"Initial_MSP", "Reset_Handler", "NMI_Handler", "HardFault_Handler",
            "MemManage_Handler", "BusFault_Handler", "UsageFault_Handler", "SecureFault_Handler",
            "Reserved8", "Reserved9", "Reserved10", "SVC_Handler", "DebugMon_Handler",
            "Reserved13", "PendSV_Handler", "SysTick_Handler"};
        int validVectors = 0;
        for (int i = 0; i < vectorWords; i++) {
            monitor.checkCancelled();
            Address slot = table.add(i * 4L);
            if (getDataAt(slot) == null && getInstructionAt(slot) == null) {
                createData(slot, DWordDataType.dataType);
            }
            String name = i < exceptions.length ? exceptions[i] : "IRQ_" + (i - 16) + "_Handler";
            setEOLComment(slot, name + ": encoded value 0x" + Long.toHexString(values[i]));
            if (i == 0 || values[i] == 0 || values[i] == 0xffffffffL || (values[i] & 1) == 0) {
                continue;
            }
            long targetValue = values[i] & ~1L;
            Address target = toAddr(targetValue);
            MemoryBlock block = memory.getBlock(target);
            if (block == null || !block.isInitialized()) {
                println("Unmapped vector target: " + slot + " -> " + target);
                continue;
            }
            validVectors++;
            currentProgram.getReferenceManager().addMemoryReference(
                slot, target, RefType.DATA, SourceType.ANALYSIS, 0);
            currentProgram.getSymbolTable().addExternalEntryPoint(target);
            if (seeded.add(targetValue)) {
                if (i >= 16 && frequency.getOrDefault(targetValue, 0) > 2) {
                    name = "Default_Handler";
                }
                disassemble(target);
                Function function = getFunctionAt(target);
                if (function == null) {
                    function = createFunction(target, name);
                } else {
                    function.setName(name, SourceType.ANALYSIS);
                }
                setPlateComment(target, "Seeded from observed vector table at " + slot +
                    "; Thumb bit removed from pointer 0x" + Long.toHexString(values[i]) + ".");
            }
        }
        setPlateComment(table, "Observed Cortex-M vector table. Initial MSP: 0x" +
            Long.toHexString(values[0]) + ". Vector names after core exceptions are provisional IRQ indices.");
        println("Prepared " + vectorWords + " vector words; valid handler slots=" + validVectors +
            ", distinct handler entry points=" + seeded.size() + ".");
    }
}
