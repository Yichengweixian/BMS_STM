// Export discovered functions, instruction bytes, data, cross-references and memory map.
// @category Firmware
// Arguments: output_directory [per_function_timeout_seconds]
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;

public class ExportFirmware extends GhidraScript {
    private String clean(Object value) {
        return String.valueOf(value).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ');
    }

    private BufferedWriter writer(Path root, String filename) throws IOException {
        return Files.newBufferedWriter(root.resolve(filename), StandardCharsets.UTF_8);
    }

    private String functionName(Address address) {
        Function function = currentProgram.getFunctionManager().getFunctionContaining(address);
        return function == null ? "" : function.getName();
    }

    private String bytesHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        final char[] digits = "0123456789abcdef".toCharArray();
        for (byte value : bytes) {
            sb.append(digits[(value & 0xff) >>> 4]).append(digits[value & 15]);
        }
        return sb.toString();
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            throw new IllegalArgumentException("ExportFirmware.java requires output_directory");
        }
        Path output = Path.of(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(output);
        int timeout = args.length > 1 ? Integer.parseInt(args[1]) : 60;
        int functionCount = 0, decompiledCount = 0, failedCount = 0;
        long instructionCount = 0, instructionBytes = 0, dataCount = 0, referenceCount = 0;
        long initializedBytes = 0;

        try (BufferedWriter out = writer(output, "memory_map.tsv")) {
            out.write("name\tstart\tend\tsize\tinitialized\tread\twrite\texecute\tvolatile\n");
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                if (block.isInitialized()) initializedBytes += block.getSize();
                out.write(clean(block.getName()) + "\t" + block.getStart() + "\t" + block.getEnd() +
                    "\t" + block.getSize() + "\t" + block.isInitialized() + "\t" + block.isRead() +
                    "\t" + block.isWrite() + "\t" + block.isExecute() + "\t" + block.isVolatile() + "\n");
            }
        }

        DecompInterface decompiler = new DecompInterface();
        DecompileOptions options = new DecompileOptions();
        options.grabFromProgram(currentProgram);
        decompiler.setOptions(options);
        decompiler.toggleCCode(true);
        decompiler.toggleSyntaxTree(true);
        if (!decompiler.openProgram(currentProgram)) {
            throw new IOException("Decompiler open failed: " + decompiler.getLastMessage());
        }
        try (BufferedWriter c = writer(output, "all_functions.c");
             BufferedWriter index = writer(output, "functions.tsv");
             BufferedWriter errors = writer(output, "decompile_errors.tsv")) {
            c.write("/* Static Ghidra decompiler output, not recovered original source.\n" +
                " * Includes discovered functions only; unrecognized code can remain.\n" +
                " * No claim of compilability, runtime equivalence, or hardware testing.\n" +
                " * Program: " + clean(currentProgram.getName()) + "; language: " +
                currentProgram.getLanguageID() + "\n */\n\n");
            index.write("entry\tname\tbody_bytes\tstatus\tprototype\n");
            errors.write("entry\tname\tmessage\n");
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                monitor.checkCancelled();
                Function function = functions.next();
                functionCount++;
                DecompileResults result = decompiler.decompileFunction(function, timeout, monitor);
                String status = "failed";
                String error = result.getErrorMessage();
                c.write("/* ENTRY " + function.getEntryPoint() + " NAME " + clean(function.getName()) + " */\n");
                if (result.decompileCompleted() && result.getDecompiledFunction() != null) {
                    decompiledCount++;
                    status = "decompiled";
                    c.write(result.getDecompiledFunction().getC());
                    c.write("\n\n");
                } else {
                    failedCount++;
                    c.write("/* DECOMPILATION FAILED: " + clean(error).replace("*/", "* /") + " */\n\n");
                }
                if (error != null && !error.isBlank()) {
                    errors.write(function.getEntryPoint() + "\t" + clean(function.getName()) + "\t" + clean(error) + "\n");
                }
                index.write(function.getEntryPoint() + "\t" + clean(function.getName()) + "\t" +
                    function.getBody().getNumAddresses() + "\t" + status + "\t" +
                    clean(function.getPrototypeString(false, false)) + "\n");
                if (functionCount % 100 == 0) println("Exported " + functionCount + " functions.");
            }
        } finally {
            decompiler.dispose();
        }

        try (BufferedWriter out = writer(output, "instructions.tsv")) {
            out.write("address\tbytes\tinstruction\tfunction\n");
            InstructionIterator instructions = currentProgram.getListing().getInstructions(true);
            while (instructions.hasNext()) {
                monitor.checkCancelled();
                Instruction instruction = instructions.next();
                instructionCount++;
                instructionBytes += instruction.getLength();
                out.write(instruction.getAddress() + "\t" + bytesHex(instruction.getBytes()) + "\t" +
                    clean(instruction) + "\t" + clean(functionName(instruction.getAddress())) + "\n");
            }
        }
        try (BufferedWriter out = writer(output, "defined_data.tsv")) {
            out.write("address\tlength\ttype\tvalue\n");
            DataIterator dataIterator = currentProgram.getListing().getDefinedData(true);
            while (dataIterator.hasNext()) {
                monitor.checkCancelled();
                Data data = dataIterator.next();
                dataCount++;
                out.write(data.getAddress() + "\t" + data.getLength() + "\t" +
                    clean(data.getDataType().getDisplayName()) + "\t" + clean(data.getDefaultValueRepresentation()) + "\n");
            }
        }
        try (BufferedWriter out = writer(output, "xrefs.tsv")) {
            out.write("from\tto\ttype\toperand\tfrom_function\tto_function\n");
            ReferenceManager references = currentProgram.getReferenceManager();
            AddressIterator sources = references.getReferenceSourceIterator(currentProgram.getMinAddress(), true);
            while (sources.hasNext()) {
                monitor.checkCancelled();
                Address source = sources.next();
                for (Reference reference : references.getReferencesFrom(source)) {
                    referenceCount++;
                    out.write(reference.getFromAddress() + "\t" + reference.getToAddress() + "\t" +
                        clean(reference.getReferenceType()) + "\t" + reference.getOperandIndex() + "\t" +
                        clean(functionName(reference.getFromAddress())) + "\t" +
                        clean(functionName(reference.getToAddress())) + "\n");
                }
            }
        }
        try (BufferedWriter out = writer(output, "summary.txt")) {
            out.write("program=" + currentProgram.getName() + "\n");
            out.write("language=" + currentProgram.getLanguageID() + "\n");
            out.write("functions=" + functionCount + "\n");
            out.write("decompiled_functions=" + decompiledCount + "\n");
            out.write("failed_functions=" + failedCount + "\n");
            out.write("instructions=" + instructionCount + "\n");
            out.write("instruction_bytes=" + instructionBytes + "\n");
            out.write("initialized_bytes=" + initializedBytes + "\n");
            out.write("defined_data_items=" + dataCount + "\n");
            out.write("references=" + referenceCount + "\n");
            out.write("scope=static analysis; discovered functions only; no target execution\n");
        }
        println("Export finished: " + output + "; " + decompiledCount + "/" + functionCount + " functions decompiled.");
    }
}
