import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.address.AddressSet;
import java.nio.file.*;
import java.io.PrintWriter;

public class FocusedPe extends GhidraScript {
    public void run() throws Exception {
        String[] args=getScriptArgs();
        var decompiler=new DecompInterface();
        decompiler.openProgram(currentProgram);
        try(var out=new PrintWriter(Files.newBufferedWriter(Path.of(args[0])))) {
            out.println("PROGRAM "+currentProgram.getName()+" SHA256 "+currentProgram.getExecutableSHA256());
            out.println("IMAGEBASE "+currentProgram.getImageBase());
            for(String line:Files.readAllLines(Path.of(args[1]))) {
                String[] parts=line.split("\t",3);
                var address=currentProgram.getImageBase().add(Long.parseLong(parts[0],16));
                int size=Integer.parseInt(parts[1]);
                var range=new AddressSet(address,address.add(size-1));
                new DisassembleCommand(address,range,true).applyTo(currentProgram,monitor);
                var function=getFunctionAt(address);
                if(function==null)function=createFunction(address,parts[2]);
                out.println("FUNCTION "+address+" size="+size+" "+parts[2]);
                if(function==null){out.println("ERROR no function");continue;}
                function.setBody(range);
                decompiler.flushCache();
                var result=decompiler.decompileFunction(function,45,monitor);
                out.println(result.decompileCompleted()?result.getDecompiledFunction().getC():result.getErrorMessage());
                out.flush();
            }
        } finally {decompiler.dispose();}
    }
}
